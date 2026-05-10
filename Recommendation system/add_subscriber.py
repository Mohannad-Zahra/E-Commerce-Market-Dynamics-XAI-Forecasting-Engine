from database.models import SessionLocal, Subscriber, init_db
init_db()
db = SessionLocal()
sub = Subscriber(email="hr58g3@gmail.com", name="Mohamed", category="laptop")
db.add(sub)
try:
    db.commit()
    print("Subscriber added")
except:
    db.rollback()
    print("Subscriber already exists")
db.close()
