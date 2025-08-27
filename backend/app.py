from fastapi import FastAPI, Depends, HTTPException, Form, Request, Response, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from PIL import Image
import secrets
import os
import shutil
import subprocess
from pathlib import Path
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Association table for many-to-many relationship between users and projects
user_projects = Table('user_projects', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Integer, default=0)
    assigned_projects = relationship("Project", secondary=user_projects, back_populates="assigned_users")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    bounding_box = Column(String)  # Format: "width x height" in meters
    table_dimension = Column(String)  # Format: "width x height" in meters
    origin = Column(String)  # Format: "x, y" in meters
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    files = relationship("UploadedFile", back_populates="project", cascade="all, delete-orphan")
    assigned_users = relationship("User", secondary=user_projects, back_populates="assigned_projects")

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    original_filename = Column(String)
    file_path = Column(String)
    thumbnail_path = Column(String)
    file_type = Column(String)
    bounding_box = Column(String)  # Format: "width x height" in meters
    origin = Column(String)  # Format: "x, y" in meters
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(String)
    project_id = Column(Integer, ForeignKey("projects.id"))
    project = relationship("Project", back_populates="files")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    user = db.query(User).filter(User.username == username).first()
    return user

def get_user_accessible_projects(user, db: Session):
    """Get projects that the user can access based on their permissions"""
    if user.is_admin:
        # Admin sees all projects
        return db.query(Project).order_by(Project.created_at.desc()).all()
    else:
        # Regular users only see assigned projects
        user_obj = db.query(User).filter(User.id == user.id).first()
        if user_obj and user_obj.assigned_projects:
            projects = user_obj.assigned_projects
            # Sort by created_at
            projects.sort(key=lambda p: p.created_at if p.created_at else datetime.min, reverse=True)
            return projects
        return []

def require_admin(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/projects", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return HTMLResponse(content='<div id="error" class="error">Invalid username or password</div>', status_code=401)
    
    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/projects", status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not user.is_admin:
        return RedirectResponse(url="/projects", status_code=302)
    
    users = db.query(User).all()
    projects = get_user_accessible_projects(user, db)
    from jinja2 import Template
    content_template = templates.get_template("admin_content.html")
    page_content = content_template.render(users=users)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": user, 
        "page_title": "User Management",
        "active_page": "admin",
        "page_content": page_content,
        "projects": projects
    })

@app.get("/users-table", response_class=HTMLResponse)
async def users_table(request: Request, db: Session = Depends(get_db), admin = Depends(require_admin)):
    users = db.query(User).all()
    return templates.TemplateResponse("users_table.html", {"request": request, "users": users})

@app.post("/users")
async def create_user(username: str = Form(...), password: str = Form(...), is_admin: str = Form(None), db: Session = Depends(get_db), admin = Depends(require_admin)):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return HTMLResponse(content='<div class="error">User already exists</div>', status_code=400)
    
    new_user = User(
        username=username,
        hashed_password=get_password_hash(password),
        is_admin=1 if is_admin else 0
    )
    db.add(new_user)
    db.commit()
    
    users = db.query(User).all()
    return templates.TemplateResponse("users_table.html", {"request": Request(scope={"type": "http"}), "users": users})

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db), admin = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == "vasnas":
        return HTMLResponse(content='<div class="error">Cannot delete the primary admin user</div>', status_code=400)
    
    db.delete(user)
    db.commit()
    
    users = db.query(User).all()
    return templates.TemplateResponse("users_table.html", {"request": Request(scope={"type": "http"}), "users": users})

@app.post("/users/{user_id}/password")
async def change_password(user_id: int, password: str = Form(...), db: Session = Depends(get_db), admin = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = get_password_hash(password)
    db.commit()
    
    return HTMLResponse(content='<div class="success">Password updated successfully</div>')

@app.get("/users/{user_id}/projects")
async def get_user_projects(user_id: int, db: Session = Depends(get_db), admin = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    all_projects = db.query(Project).order_by(Project.name).all()
    assigned_project_ids = [p.id for p in user.assigned_projects]
    
    return JSONResponse(content={
        "all_projects": [{"id": p.id, "name": p.name} for p in all_projects],
        "assigned_project_ids": assigned_project_ids
    })

@app.post("/users/{user_id}/projects")
async def assign_projects(
    user_id: int, 
    project_ids: str = Form(""),
    db: Session = Depends(get_db), 
    admin = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Clear existing assignments
    user.assigned_projects.clear()
    
    # Add new assignments
    if project_ids:
        project_id_list = [int(pid.strip()) for pid in project_ids.split(',') if pid.strip()]
        projects = db.query(Project).filter(Project.id.in_(project_id_list)).all()
        user.assigned_projects.extend(projects)
    
    db.commit()
    return JSONResponse(content={"message": "Projects assigned successfully"})

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Get the actual user object with relationships
    user_obj = db.query(User).filter(User.id == user.id).first()
    
    # Admin sees all projects, regular users see only assigned projects
    if user.is_admin:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
    else:
        # Regular users only see assigned projects (not their created ones)
        assigned_projects = user_obj.assigned_projects if user_obj else []
        projects = assigned_projects
        projects.sort(key=lambda p: p.created_at if p.created_at else datetime.min, reverse=True)
    content_template = templates.get_template("projects_content.html")
    page_content = content_template.render(projects=projects, user=user)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "page_title": "Projects",
        "active_page": "projects",
        "page_content": page_content,
        "projects": projects[:10]  # Show max 10 projects in sidebar
    })

@app.get("/projects-table", response_class=HTMLResponse)
async def projects_table(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    
    # Use the same logic as the projects_page to get accessible projects
    user_obj = db.query(User).filter(User.id == user.id).first()
    if user.is_admin:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
    else:
        # Regular users only see assigned projects
        projects = user_obj.assigned_projects if user_obj else []
        projects.sort(key=lambda p: p.created_at if p.created_at else datetime.min, reverse=True)
    return templates.TemplateResponse("projects_table.html", {"request": request, "projects": projects, "user": user})

@app.post("/projects")
async def create_project(
    name: str = Form(...), 
    description: str = Form(""),
    bounding_box: str = Form(""),
    table_dimension: str = Form(""),
    origin: str = Form(""),
    db: Session = Depends(get_db), 
    request: Request = None
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    
    new_project = Project(
        name=name,
        description=description,
        bounding_box=bounding_box,
        table_dimension=table_dimension,
        origin=origin,
        created_by=user.username
    )
    db.add(new_project)
    db.commit()
    
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return templates.TemplateResponse("projects_table.html", {"request": Request(scope={"type": "http"}), "projects": projects, "user": user})

@app.delete("/projects/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db), request: Request = None):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not user.is_admin and project.created_by != user.username:
        return HTMLResponse(content='<div class="error">You can only delete your own projects</div>', status_code=403)
    
    db.delete(project)
    db.commit()
    
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return templates.TemplateResponse("projects_table.html", {"request": Request(scope={"type": "http"}), "projects": projects, "user": user})

@app.put("/projects/{project_id}")
async def update_project(
    project_id: int, 
    name: str = Form(...), 
    description: str = Form(""),
    bounding_box: str = Form(""),
    table_dimension: str = Form(""),
    origin: str = Form(""),
    db: Session = Depends(get_db), 
    request: Request = None
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not user.is_admin and project.created_by != user.username:
        return HTMLResponse(content='<div class="error">You can only edit your own projects</div>', status_code=403)
    
    project.name = name
    project.description = description
    project.bounding_box = bounding_box
    project.table_dimension = table_dimension
    project.origin = origin
    db.commit()
    
    return HTMLResponse(content='<div class="success">Project updated successfully</div>')

@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=302)
    
    # Check if user has access to this project
    if not user.is_admin:
        user_obj = db.query(User).filter(User.id == user.id).first()
        assigned_project_ids = [p.id for p in user_obj.assigned_projects] if user_obj else []
        if project.id not in assigned_project_ids and project.created_by != user.username:
            return RedirectResponse(url="/projects", status_code=302)
    
    uploaded_files = db.query(UploadedFile).filter(UploadedFile.project_id == project_id).order_by(UploadedFile.uploaded_at.desc()).all()
    sidebar_projects = get_user_accessible_projects(user, db)
    content_template = templates.get_template("project_detail.html")
    page_content = content_template.render(project=project, user=user, uploaded_files=uploaded_files)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "page_title": project.name,
        "active_page": "projects",
        "active_project_id": project_id,
        "page_content": page_content,
        "projects": sidebar_projects
    })

def generate_image_thumbnail(input_path: str, output_path: str, size=(200, 200)):
    try:
        with Image.open(input_path) as img:
            # Convert RGBA to RGB if needed for JPEG output
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(output_path, 'JPEG', quality=85)
        return True
    except Exception as e:
        print(f"Error generating image thumbnail: {e}")
        return False

def generate_video_thumbnail(input_path: str, output_path: str, size=(200, 200)):
    try:
        # First try to use ffmpeg if available
        import shutil
        if shutil.which('ffmpeg'):
            cmd = [
                'ffmpeg', '-i', input_path,
                '-ss', '00:00:01',
                '-vframes', '1',
                '-vf', f'scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2',
                '-y',
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
            else:
                print(f"ffmpeg error: {result.stderr}")
        
        # Fallback: create a video placeholder thumbnail
        print("ffmpeg not available, using placeholder")
        placeholder_path = "static/video_placeholder.jpg"
        if os.path.exists(placeholder_path):
            shutil.copy(placeholder_path, output_path)
            return True
        else:
            # Create a simple placeholder if the file doesn't exist
            from PIL import Image, ImageDraw
            img = Image.new('RGB', size, color='#4a5568')
            draw = ImageDraw.Draw(img)
            # Draw a play button
            w, h = size
            triangle = [(w*0.4, h*0.35), (w*0.4, h*0.65), (w*0.6, h*0.5)]
            draw.polygon(triangle, fill='white')
            img.save(output_path, 'JPEG', quality=85)
            return True
            
    except Exception as e:
        print(f"Error generating video thumbnail: {e}")
        return False

@app.delete("/files/{file_id}")
async def delete_file(file_id: int, request: Request = None, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    
    uploaded_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not uploaded_file:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    
    project = db.query(Project).filter(Project.id == uploaded_file.project_id).first()
    if not project:
        return JSONResponse(content={"error": "Project not found"}, status_code=404)
    
    if not user.is_admin and project.created_by != user.username:
        return JSONResponse(content={"error": "Permission denied"}, status_code=403)
    
    # Delete physical files
    try:
        if os.path.exists(uploaded_file.file_path):
            os.remove(uploaded_file.file_path)
        if os.path.exists(uploaded_file.thumbnail_path):
            os.remove(uploaded_file.thumbnail_path)
    except Exception as e:
        print(f"Error deleting files: {e}")
    
    # Delete database record
    db.delete(uploaded_file)
    db.commit()
    
    return JSONResponse(content={"success": True, "message": "File deleted successfully"})

def parse_bounding_box(bbox_str):
    """Parse bounding box string 'width x height' and return (width, height) as floats"""
    if not bbox_str:
        return None, None
    try:
        parts = bbox_str.lower().replace('×', 'x').split('x')
        if len(parts) != 2:
            return None, None
        width = float(parts[0].strip())
        height = float(parts[1].strip())
        return width, height
    except:
        return None, None

def parse_origin(origin_str):
    """Parse origin string 'x, y' and return (x, y) as floats"""
    if not origin_str:
        return None, None
    try:
        parts = origin_str.replace('(', '').replace(')', '').split(',')
        if len(parts) != 2:
            return None, None
        x = float(parts[0].strip())
        y = float(parts[1].strip())
        return x, y
    except:
        return None, None

def validate_image_placement(image_bbox_str, image_origin_str, project_bbox_str, project_origin_str):
    """Check if image fits within project boundaries considering both bounding box and origin"""
    # Parse image dimensions and origin
    img_width, img_height = parse_bounding_box(image_bbox_str)
    img_x, img_y = parse_origin(image_origin_str)
    
    # Parse project dimensions and origin
    proj_width, proj_height = parse_bounding_box(project_bbox_str)
    proj_x, proj_y = parse_origin(project_origin_str)
    
    # Validate image data
    if img_width is None or img_height is None:
        return False, "Invalid image bounding box format. Use 'width x height' (e.g., '10 x 5')"
    
    if img_x is None or img_y is None:
        return False, "Invalid image origin format. Use 'x, y' (e.g., '0, 0')"
    
    # Validate project data
    if proj_width is None or proj_height is None:
        return False, "Project does not have a valid bounding box defined"
    
    # Use default origin (0, 0) if project origin is not specified
    if proj_x is None or proj_y is None:
        proj_x, proj_y = 0, 0
    
    # Check if image dimensions exceed project dimensions
    if img_width > proj_width or img_height > proj_height:
        return False, f"Image dimensions ({img_width} x {img_height}m) exceed project dimensions ({proj_width} x {proj_height}m)"
    
    # Calculate image boundaries
    img_left = img_x
    img_right = img_x + img_width
    img_bottom = img_y
    img_top = img_y + img_height
    
    # Calculate project boundaries
    proj_left = proj_x
    proj_right = proj_x + proj_width
    proj_bottom = proj_y
    proj_top = proj_y + proj_height
    
    # Check if image is completely within project boundaries
    if img_left < proj_left or img_right > proj_right or img_bottom < proj_bottom or img_top > proj_top:
        return False, (f"Image placement is outside project boundaries. "
                      f"Image spans from ({img_left}, {img_bottom}) to ({img_right}, {img_top}), "
                      f"but project boundaries are from ({proj_left}, {proj_bottom}) to ({proj_right}, {proj_top})")
    
    return True, "Valid"

@app.post("/ingest/direct")
async def upload_file(
    file: UploadFile = File(...),
    project_id: int = Form(...),
    bounding_box: str = Form(...),
    origin: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return JSONResponse(content={"error": "Project not found"}, status_code=404)
    
    if not user.is_admin and project.created_by != user.username:
        return JSONResponse(content={"error": "Permission denied"}, status_code=403)
    
    # Validate image placement within project boundaries
    is_valid, error_msg = validate_image_placement(
        bounding_box, origin, project.bounding_box, project.origin
    )
    if not is_valid:
        return JSONResponse(content={"error": error_msg}, status_code=400)
    
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.mp4', '.webm', '.mov'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        return JSONResponse(
            content={"error": f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"},
            status_code=400
        )
    
    unique_id = str(uuid.uuid4())
    safe_filename = f"{unique_id}{file_ext}"
    file_path = f"static/assets/{safe_filename}"
    thumbnail_path = f"static/assets/thumbnails/{unique_id}_thumb.jpg"
    
    os.makedirs("static/assets", exist_ok=True)
    os.makedirs("static/assets/thumbnails", exist_ok=True)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        if file_ext in ['.png', '.jpg', '.jpeg']:
            generate_image_thumbnail(file_path, thumbnail_path)
            file_type = "image"
        elif file_ext in ['.mp4', '.webm', '.mov']:
            generate_video_thumbnail(file_path, thumbnail_path)
            file_type = "video"
        
        uploaded_file = UploadedFile(
            filename=safe_filename,
            original_filename=file.filename,
            file_path=file_path,
            thumbnail_path=thumbnail_path,
            file_type=file_type,
            bounding_box=bounding_box,
            origin=origin,
            uploaded_by=user.username,
            project_id=project_id
        )
        db.add(uploaded_file)
        db.commit()
        
        return JSONResponse(content={
            "success": True,
            "file_id": uploaded_file.id,
            "filename": uploaded_file.original_filename,
            "thumbnail": f"/{thumbnail_path}"
        })
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        return JSONResponse(content={"error": str(e)}, status_code=500)

def init_admin_user():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "vasnas").first()
        if not admin:
            admin_password = secrets.token_urlsafe(12)
            admin_user = User(
                username="vasnas",
                hashed_password=get_password_hash(admin_password),
                is_admin=1
            )
            db.add(admin_user)
            db.commit()
            print(f"\n{'='*50}")
            print(f"Admin user created!")
            print(f"Username: vasnas")
            print(f"Password: {admin_password}")
            print(f"{'='*50}\n")
            return admin_password
    finally:
        db.close()

if __name__ == "__main__":
    admin_password = init_admin_user()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)