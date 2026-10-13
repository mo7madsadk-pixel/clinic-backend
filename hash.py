from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.hash("123456")) # يمكنك تغيير 123456 لأي كلمة مرور تريدها