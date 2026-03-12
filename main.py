import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request, Form, File, UploadFile, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from auth import hash_password, verify_password
from rag import build_index, generate_answer
from export import export_documents

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UPLOAD_QUESTION_FOLDER = os.path.join(BASE_DIR, "uploads", "questionnaire")
UPLOAD_REFERENCE_FOLDER = os.path.join(BASE_DIR, "uploads", "references")
EXPORT_FOLDER = os.path.join(BASE_DIR, "exports")

os.makedirs(UPLOAD_QUESTION_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_REFERENCE_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    try:
        return db.query(models.User).filter(models.User.id == int(user_id)).first()
    except Exception:
        return None


# ---- AUTH ----

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Email already registered. Please log in."
        })
    if len(password) < 6:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Password must be at least 6 characters."
        })

    user = models.User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("user_id", str(user.id), httponly=True, samesite="lax")
    return response


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid email or password."
        })

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("user_id", str(user.id), httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_id")
    return response


# ---- DASHBOARD ----

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    runs = db.query(models.Run).filter(models.Run.user_id == user.id)\
              .order_by(models.Run.id.desc()).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "runs": runs
    })


# ---- UPLOAD & GENERATE ----

@app.post("/upload")
async def upload(
    request: Request,
    questionnaire: UploadFile = File(...),
    references: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    # Save questionnaire
    q_filename = f"{user.id}_{questionnaire.filename}"
    q_path = os.path.join(UPLOAD_QUESTION_FOLDER, q_filename)
    content = await questionnaire.read()
    with open(q_path, "wb") as f:
        f.write(content)

    # Save reference files into user-specific subfolder
    user_ref_folder = os.path.join(UPLOAD_REFERENCE_FOLDER, str(user.id))
    os.makedirs(user_ref_folder, exist_ok=True)

    for old_file in os.listdir(user_ref_folder):
        os.remove(os.path.join(user_ref_folder, old_file))

    for ref in references:
        r_path = os.path.join(user_ref_folder, ref.filename)
        ref_content = await ref.read()
        with open(r_path, "wb") as f:
            f.write(ref_content)

    # Build FAISS index
    index, texts, sources = build_index(user_ref_folder)

    # Parse questions
    try:
        text_content = content.decode("utf-8", errors="ignore")
    except Exception:
        text_content = ""

    questions = [q.strip() for q in text_content.splitlines() if q.strip()]

    if not questions:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "runs": [],
            "error": "No questions found. Upload a .txt file with one question per line."
        })

    # Create run
    run = models.Run(user_id=user.id, questionnaire_name=questionnaire.filename)
    db.add(run)
    db.commit()
    db.refresh(run)

    # --- PARALLEL answer generation ---
    results_map = {}

    def answer_question(idx_q):
        idx, q = idx_q
        return idx, generate_answer(q, index, texts, sources)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(answer_question, (i, q)): i for i, q in enumerate(questions)}
        for future in as_completed(futures):
            idx, result = future.result()
            results_map[idx] = result

    # Insert answers in original order
    for i, q in enumerate(questions):
        result = results_map.get(i, {})
        ans = models.Answer(
            user_id=user.id,
            run_id=run.id,
            question=q,
            answer=result.get("answer", ""),
            citation=result.get("citation", ""),
            confidence=result.get("confidence", "0.0"),
            evidence=result.get("evidence", "")
        )
        db.add(ans)

    db.commit()

    return RedirectResponse(url=f"/results/{run.id}", status_code=303)


# ---- RESULTS ----

@app.get("/results/{run_id}", response_class=HTMLResponse)
def results(run_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    run = db.query(models.Run).filter(
        models.Run.id == run_id, models.Run.user_id == user.id
    ).first()
    if not run:
        return RedirectResponse(url="/dashboard", status_code=303)

    answers = db.query(models.Answer).filter(
        models.Answer.run_id == run_id,
        models.Answer.user_id == user.id
    ).all()

    total = len(answers)
    answered = sum(1 for a in answers if a.answer and "not found" not in a.answer.lower())
    not_found = total - answered

    return templates.TemplateResponse("results.html", {
        "request": request,
        "user": user,
        "run": run,
        "answers": answers,
        "total": total,
        "answered": answered,
        "not_found": not_found
    })


# ---- EDIT ANSWER ----

@app.post("/edit/{answer_id}")
async def edit_answer(
    answer_id: int,
    request: Request,
    answer: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    ans = db.query(models.Answer).filter(
        models.Answer.id == answer_id,
        models.Answer.user_id == user.id
    ).first()

    if ans:
        ans.answer = answer.strip()
        db.commit()

    return RedirectResponse(url=f"/results/{ans.run_id}" if ans else "/dashboard", status_code=303)


# ---- REGENERATE SINGLE ANSWER ----

@app.post("/regenerate/{answer_id}")
async def regenerate_answer(
    answer_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    ans = db.query(models.Answer).filter(
        models.Answer.id == answer_id,
        models.Answer.user_id == user.id
    ).first()

    if not ans:
        return JSONResponse({"error": "Answer not found"}, status_code=404)

    user_ref_folder = os.path.join(UPLOAD_REFERENCE_FOLDER, str(user.id))
    index, texts, sources = build_index(user_ref_folder)
    result = generate_answer(ans.question, index, texts, sources)

    ans.answer = result.get("answer", "")
    ans.citation = result.get("citation", "")
    ans.confidence = result.get("confidence", "0.0")
    ans.evidence = result.get("evidence", "")
    db.commit()

    return RedirectResponse(url=f"/results/{ans.run_id}", status_code=303)


# ---- EXPORT ----

@app.get("/export/{run_id}")
def export(run_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    run = db.query(models.Run).filter(
        models.Run.id == run_id, models.Run.user_id == user.id
    ).first()
    if not run:
        return RedirectResponse(url="/dashboard", status_code=303)

    answers = db.query(models.Answer).filter(
        models.Answer.run_id == run_id,
        models.Answer.user_id == user.id
    ).all()

    output_file = export_documents(answers, run, EXPORT_FOLDER)

    return FileResponse(
        path=output_file,
        filename=f"questionnaire_answers_run{run_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )