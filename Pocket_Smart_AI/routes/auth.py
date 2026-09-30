import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import JSONResponse

from ..deps import current_user

from ..models.schemas import (
    HomeRequest,
    JewelryRequest,
    LoginRequest,
    PartyRequest,
    RegisterRequest,
)

from ..security import (
    create_access_token,
    hash_password,
    verify_password,
)

from ..services.recommender import recommend

from ..services.store import (
    create_user,
    get_user_by_email,
    history,
    recommendation,
    save_recommendation,
)


router = APIRouter(
    prefix="/api",
    tags=["PocketSmart AI"],
)


@router.post("/register")
def register(
    data: RegisterRequest,
):

    existing = get_user_by_email(
        data.email
    )

    if existing:

        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    user_id = create_user(
        data.name,
        data.email,
        hash_password(data.password),
    )

    return {
        "message": "Registration successful",
        "user_id": user_id,
    }


def login_response(user):

    token = create_access_token(
        user["id"]
    )

    response = JSONResponse(
        {
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
            },
        }
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return response


@router.post("/login")
def login(
    data: LoginRequest,
):

    user = get_user_by_email(
        data.email
    )

    if (
        not user
        or not verify_password(
            data.password,
            user["password_hash"],
        )
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    return login_response(user)


@router.post("/token")
def token(
    data: LoginRequest,
):

    user = get_user_by_email(
        data.email
    )

    if (
        not user
        or not verify_password(
            data.password,
            user["password_hash"],
        )
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    return {
        "access_token": create_access_token(
            user["id"]
        ),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout():

    response = JSONResponse(
        {
            "message": "Logged out"
        }
    )

    response.delete_cookie(
        "access_token"
    )

    return response


@router.get("/session-info")
def session_info(
    user=Depends(current_user),
):

    return {
        "logged_in": True,
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
    }


@router.get("/session-data")
def session_data(
    user=Depends(current_user),
):

    rows = history(
        user["id"]
    )

    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        },
        "recommendation_count": len(rows),
    }


async def save_and_return(
    planner,
    data,
    user,
    image_bytes=None,
    image_mime=None,
):

    result = await recommend(
        planner,
        data,
        image_bytes,
        image_mime,
    )

    recommendation_id = save_recommendation(
        user["id"],
        planner,
        data.model_dump(),
        result,
    )

    result["id"] = recommendation_id

    return result


@router.post("/generate-home")
async def generate_home(
    data: HomeRequest,
    user=Depends(current_user),
):

    return await save_and_return(
        "home",
        data,
        user,
    )


@router.post("/generate-party")
async def generate_party(
    data: PartyRequest,
    user=Depends(current_user),
):

    return await save_and_return(
        "party",
        data,
        user,
    )


@router.post("/generate-jewelry")
async def generate_jewelry(
    budget: float = Form(...),
    occasion: str = Form(...),
    style: str = Form("elegant"),
    outfit_description: str = Form(""),
    image: UploadFile | None = File(None),
    user=Depends(current_user),
):

    if budget <= 0:

        raise HTTPException(
            status_code=422,
            detail="Budget must be greater than zero",
        )

    if not occasion.strip():

        raise HTTPException(
            status_code=422,
            detail="Occasion is required",
        )

    image_bytes = None
    image_mime = None

    if image:

        image_bytes = await image.read()

        image_mime = (
            image.content_type
            or "image/jpeg"
        )

    data = JewelryRequest(
        budget=budget,
        occasion=occasion,
        style=style,
        outfit_description=outfit_description,
    )

    return await save_and_return(
        "jewelry",
        data,
        user,
        image_bytes,
        image_mime,
    )


@router.get("/history")
def get_history(
    user=Depends(current_user),
):

    items = []

    for row in history(user["id"]):

        request_data = json.loads(
            row["request_json"]
        )

        response_data = json.loads(
            row["response_json"]
        )

        items.append(
            {
                "id": row["id"],
                "planner": row["planner"],
                "request": request_data,
                "response": response_data,
                "created_at": row["created_at"],
            }
        )

    return {
        "items": items
    }


@router.get(
    "/recommendations-details/{recommendation_id}"
)
def recommendation_details(
    recommendation_id: int,
    user=Depends(current_user),
):

    row = recommendation(
        user["id"],
        recommendation_id,
    )

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Recommendation not found",
        )

    return {
        "id": row["id"],
        "planner": row["planner"],
        "request": json.loads(
            row["request_json"]
        ),
        "response": json.loads(
            row["response_json"]
        ),
        "created_at": row["created_at"],
    }