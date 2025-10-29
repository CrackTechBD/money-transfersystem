from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from common.security import mint_user_jwt, verify_token

app = FastAPI(title="Auth Service")

class LoginRequest(BaseModel):
    user_id: str

@app.post("/login")
async def login(req: LoginRequest):
    # TODO: add real authentication in production
    token = mint_user_jwt(sub=req.user_id, claims={"scope": "user"})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/introspect")
async def introspect(token: str):
    try:
        return verify_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
