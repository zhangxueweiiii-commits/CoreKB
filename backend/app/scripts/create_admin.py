import os

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def main() -> None:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD")
    email = os.getenv("ADMIN_EMAIL")
    if not password:
        raise SystemExit("ADMIN_PASSWORD is required")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user:
            user.password_hash = get_password_hash(password)
            user.role = UserRole.admin
            user.is_active = True
        else:
            user = User(
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(user)
        db.commit()
    print(f"Admin user ready: {username}")


if __name__ == "__main__":
    main()
