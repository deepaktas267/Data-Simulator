from celery import Celery
from datetime import datetime
import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from faker import Faker
import random
from fastapi.responses import FileResponse
from typing import Dict, List, Optional
import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, validator
from dotenv import load_dotenv
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware


# Initialize Celery
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Initialize FastAPI
app = FastAPI()
fake = Faker()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Models
class ColumnSchema(BaseModel):
    name: str
    type: str
    mode: Optional[str] = "NULLABLE"
    constraints: Optional[Dict] = None

class TableSchema(BaseModel):
    table_name: str
    fields: List[ColumnSchema]

class DataGenerationRequest(BaseModel):
    schema: TableSchema
    record_count: int
    output_format: str = "both"  # "csv", "json", or "both"

# Data Generation Functions
def generate_field_value(field: Dict) -> any:
    """Generate value for a single field"""
    field_name = field["name"]
    field_type = field["type"]
    
    if "ID" in field_name and field.get("constraints") and "pattern" in field["constraints"]:
        pattern = field["constraints"]["pattern"]
        if pattern == "^CUST-[0-9]{5}$":
            return f"CUST-{random.randint(10000, 99999)}"
        elif pattern == "^PROD-[0-9]{5}$":
            return f"PROD-{random.randint(10000, 99999)}"
        elif pattern == "^ORD-[0-9]{5}-[0-9]{5}$":
            return f"ORD-{random.randint(10000, 99999)}-{random.randint(10000, 99999)}"
    
    if field_type == "STRING":
        if field_name == "Email":
            return fake.email()
        elif field_name == "Location":
            return fake.city()
        return fake.name()
    
    elif field_type == "INTEGER":
        return random.randint(1, 100)
    
    elif field_type == "DECIMAL":
        return round(random.uniform(1, 1000), 2)
    
    elif field_type == "DATE":
        return fake.date_this_year().isoformat()
    
    elif field_type == "BOOLEAN":
        return random.choice([True, False])
    
    return None

def generate_record(schema: Dict) -> Dict:
    """Generate a single record based on schema"""
    return {field["name"]: generate_field_value(field) for field in schema["fields"]}

def save_data(data: List[Dict], base_filename: str, output_format: str) -> Dict:
    """Save data in specified formats and return file paths"""
    os.makedirs("generated_data", exist_ok=True)
    result = {}
    
    if output_format in ["csv", "both"]:
        csv_path = f"generated_data/{base_filename}.csv"
        pd.DataFrame(data).to_csv(csv_path, index=False)
        result["csv"] = csv_path
    
    if output_format in ["json", "both"]:
        json_path = f"generated_data/{base_filename}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        result["json"] = json_path
    
    return result

# Celery Task
@celery_app.task(bind=True)
def generate_data_task(self, schema, count, output_format):
    try:
        # Generate sample record for preview
        sample_record = generate_record(schema)
        preview_csv = "\n".join([
            ",".join(sample_record.keys()),
            ",".join(str(v) for v in sample_record.values())
        ])
        
        # Generate full dataset with progress updates
        data = []
        for i in range(count):
            data.append(generate_record(schema))
            if i % 100 == 0 or i == count - 1:
                self.update_state(state='PROGRESS', meta={
                    'current': i + 1,
                    'total': count,
                    'status': f'Generated {i+1}/{count} records'
                })
        
        # Save files with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{schema['table_name'].lower()}_{timestamp}"
        files = save_data(data, base_filename, output_format)
        
        return {
            "status": "success",
            "records_generated": count,
            "files": files,
            "sample_record": sample_record,
            "previews": {
                "schema_json": json.dumps(schema, indent=2),
                "sample_csv": preview_csv
            },
            "schema": schema
        }
    except Exception as e:
        return {'error': str(e)}

# API Endpoints
@app.post("/generate-data/")
async def generate_data(request: DataGenerationRequest):
    """Synchronous generation endpoint"""
    try:
        schema_dict = request.schema.dict()
        
        # Generate sample record for preview
        sample_record = generate_record(schema_dict)
        preview_csv = "\n".join([
            ",".join(sample_record.keys()),
            ",".join(str(v) for v in sample_record.values())
        ])
        
        # Generate full dataset
        data = [generate_record(schema_dict) for _ in range(request.record_count)]
        
        # Save files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{request.schema.table_name.lower()}_{timestamp}"
        files = save_data(data, base_filename, request.output_format)
        
        return {
            "status": "success",
            "records_generated": request.record_count,
            "files": files,
            "sample_record": sample_record,
            "previews": {
                "schema_json": json.dumps(schema_dict, indent=2),
                "sample_csv": preview_csv
            },
            "schema": schema_dict
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-data-async/")
async def generate_data_async(request: DataGenerationRequest):
    """Asynchronous generation endpoint"""
    try:
        task = generate_data_task.delay(
            request.schema.dict(),
            request.record_count,
            request.output_format
        )
        return {"task_id": task.id, "status": "Task started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Check task status"""
    task_result = generate_data_task.AsyncResult(task_id)
    
    if task_result.ready():
        result = task_result.result
        if 'error' in result:
            return {
                "task_id": task_id,
                "status": "FAILURE",
                "error": result['error']
            }
        return {
            "task_id": task_id,
            "status": task_result.status,
            "result": result  # Same structure as sync endpoint
        }
    
    progress = task_result.info if isinstance(task_result.info, dict) else {}
    return {
        "task_id": task_id,
        "status": task_result.status,
        "progress": progress.get('current', 0),
        "total": progress.get('total', 1),
        "message": progress.get('status', 'Processing')
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated file"""
    file_path = f"generated_data/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

@app.get("/")
async def health_check():
    return {"status": "healthy"}


load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
OTP_EXPIRE_MINUTES = 5

# SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

otp_storage = {}



# Models
class EmailRequest(BaseModel):
    email: EmailStr

class OTPVerification(BaseModel):
    email: EmailStr
    otp: str

# Utility functions
def generate_otp(length=6):
    return ''.join(random.choices('0123456789', k=length))

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USERNAME
    msg['To'] = to_email
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}"
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Endpoints
@app.post("/send-otp")
async def send_otp(request: EmailRequest):
    email = request.email
    otp = generate_otp()
    expiration_time = datetime.now() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    
    # Store OTP with expiration
    otp_storage[email] = {
        "otp": otp,
        "expires_at": expiration_time
    }
    
    # Send OTP via email
    subject = "Your OTP Code"
    body = f"Your OTP code is: {otp}. It will expire in {OTP_EXPIRE_MINUTES} minutes."
    
    send_email(email, subject, body)
    
    return {"message": "OTP sent successfully", "email": email}

@app.post("/verify-otp")
async def verify_otp(request: OTPVerification):
    email = request.email
    user_otp = request.otp
    
    stored_otp_data = otp_storage.get(email)
    
    if not stored_otp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found or expired. Please request a new OTP."
        )
    
    if datetime.now() > stored_otp_data["expires_at"]:
        del otp_storage[email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new OTP."
        )
    
    if user_otp != stored_otp_data["otp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP."
        )
    
    # OTP is valid, generate JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email}, expires_delta=access_token_expires
    )
    
    # Clean up OTP
    del otp_storage[email]
    
    return {
        "message": "OTP verified successfully",
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.get("/protected")
async def protected_route(token: str = Depends(OAuth2PasswordBearer(tokenUrl="verify-otp"))):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"message": "You have accessed protected content", "email": email}



from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["endpoint"])

# Middleware for tracking requests
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        REQUEST_COUNT.labels(request.method, request.url.path).inc()
        REQUEST_LATENCY.labels(request.url.path).observe(duration)
        
        return response

# Add middleware
app.add_middleware(PrometheusMiddleware)

# Prometheus Metrics Endpoint
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)