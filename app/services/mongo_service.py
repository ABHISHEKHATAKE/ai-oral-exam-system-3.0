from typing import Optional, List, Dict
import os
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
DB_NAME = os.getenv("MONGODB_DB") or "exam_system_db"

class MongoService:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self._connect()

    def _connect(self):
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Trigger connection attempt
            self.client.server_info()
            self.db = self.client[DB_NAME]
            # Ensure indexes
            self.db.students.create_index("student_id", unique=True)
            self.db.instructors.create_index("instructor_id", unique=True)
            self.db.users.create_index("username", unique=True)
        except ServerSelectionTimeoutError:
            self.client = None
            self.db = None
            print(f"⚠️ Could not connect to MongoDB at {MONGODB_URI}. Running without DB persistence.")

    def is_connected(self) -> bool:
        return self.client is not None and self.db is not None

    # Student operations
    def create_student(self, student: Dict) -> bool:
        if not self.is_connected():
            return False
        students = self.db.students
        try:
            # Upsert by student_id
            students.update_one({"student_id": student["student_id"]}, {"$set": student}, upsert=True)
            return True
        except Exception as e:
            print(f"Error creating student in MongoDB: {e}")
            return False

    def get_student_by_email(self, email: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        return self.db.students.find_one({"email": email})

    def get_student_by_id(self, student_id: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        return self.db.students.find_one({"student_id": student_id})

    def list_students(self) -> List[Dict]:
        if not self.is_connected():
            return []
        docs = list(self.db.students.find({}))
        # Convert any ObjectId fields if present - keep as-is since we store string ids
        for d in docs:
            d.pop("_id", None)
        return docs

    # User operations (for auth)
    def create_user(self, user: Dict) -> bool:
        if not self.is_connected():
            return False
        try:
            self.db.users.update_one({"username": user["username"]}, {"$set": user}, upsert=True)
            return True
        except Exception as e:
            print(f"Error creating user in MongoDB: {e}")
            return False

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        user = self.db.users.find_one({"username": username})
        if user:
            user.pop("_id", None)
        return user


    # Instructor operations
    def create_instructor(self, instructor: Dict) -> bool:
        if not self.is_connected():
            return False
        try:
            self.db.instructors.update_one({"instructor_id": instructor["instructor_id"]}, {"$set": instructor}, upsert=True)
            return True
        except Exception as e:
            print(f"Error creating instructor in MongoDB: {e}")
            return False

    def list_instructors(self) -> List[Dict]:
        if not self.is_connected():
            return []
        docs = list(self.db.instructors.find({}))
        for d in docs:
            d.pop("_id", None)
        return docs

    # PDF exam operations
    def create_pdf_exam(self, exam: Dict) -> bool:
        if not self.is_connected():
            return False
        try:
            self.db.pdf_exams.update_one({"exam_id": exam["exam_id"]}, {"$set": exam}, upsert=True)
            return True
        except Exception as e:
            print(f"Error creating pdf exam in MongoDB: {e}")
            return False

    def get_pdf_exams_by_student(self, student_id: str) -> List[Dict]:
        if not self.is_connected():
            return []
        docs = list(self.db.pdf_exams.find({"student_id": student_id}))
        for d in docs:
            d.pop("_id", None)
        return docs

    def get_pdf_exam_by_id(self, exam_id: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        doc = self.db.pdf_exams.find_one({"exam_id": exam_id})
        if doc:
            doc.pop("_id", None)
        return doc

    def get_all_pdf_exams(self) -> List[Dict]:
        if not self.is_connected():
            return []
        docs = list(self.db.pdf_exams.find({}))
        for d in docs:
            d.pop("_id", None)
        return docs

    # Completed exams operations
    def create_completed_exam(self, exam: Dict) -> bool:
        if not self.is_connected():
            return False
        try:
            self.db.completed_exams.update_one({"exam_id": exam["exam_id"]}, {"$set": exam}, upsert=True)
            return True
        except Exception as e:
            print(f"Error creating completed exam in MongoDB: {e}")
            return False

    def get_completed_exams_by_student(self, student_id: str) -> List[Dict]:
        if not self.is_connected():
            return []
        docs = list(self.db.completed_exams.find({"student_id": student_id}))
        for d in docs:
            d.pop("_id", None)
        return docs

    def get_completed_exam_by_id(self, exam_id: str) -> Optional[Dict]:
        """Get a completed exam by exam_id"""
        if not self.is_connected():
            return None
        doc = self.db.completed_exams.find_one({"exam_id": exam_id})
        if doc:
            doc.pop("_id", None)
        return doc

    def get_all_completed_exams(self) -> List[Dict]:
        """Get all completed exams"""
        if not self.is_connected():
            return []
        docs = list(self.db.completed_exams.find({}))
        for d in docs:
            d.pop("_id", None)
        return docs

    def get_all_completed_pdf_exams(self) -> List[Dict]:
        if not self.is_connected():
            return []
        try:
            docs = list(self.db.completed_pdf_exams.find({}))
            for d in docs:
                d.pop("_id", None)
            return docs
        except Exception as e:
            print(f"Error getting completed PDF exams from MongoDB: {e}")
            return []
    def create_exam_schedule(self, schedule: Dict) -> bool:
        if not self.is_connected():
            return False
        try:
            self.db.exam_schedules.update_one({"student_id": schedule["student_id"]}, {"$set": schedule}, upsert=True)
            return True
        except Exception as e:
            print(f"Error creating exam schedule in MongoDB: {e}")
            return False

    def get_exam_schedule(self, student_id: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        doc = self.db.exam_schedules.find_one({"student_id": student_id})
        if doc:
            doc.pop("_id", None)
        return doc

    def delete_exam_schedule(self, student_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            self.db.exam_schedules.delete_one({"student_id": student_id})
            return True
        except Exception as e:
            print(f"Error deleting exam schedule in MongoDB: {e}")
            return False

    def update_student_id(self, old_student_id: str, new_student_id: str) -> bool:
        """
        Migrate a student's identifier across collections.
        Returns True on success, False on failure.
        """
        if not self.is_connected():
            return False
        try:
            # Update students collection (change the student_id field)
            students = self.db.students
            # Ensure target id does not exist
            if students.find_one({"student_id": new_student_id}):
                print(f"Error: target student_id {new_student_id} already exists in DB")
                return False

            res = students.update_one({"student_id": old_student_id}, {"$set": {"student_id": new_student_id}})

            # Update related collections that reference student_id
            try:
                self.db.pdf_exams.update_many({"student_id": old_student_id}, {"$set": {"student_id": new_student_id}})
            except Exception:
                pass
            try:
                self.db.completed_exams.update_many({"student_id": old_student_id}, {"$set": {"student_id": new_student_id}})
            except Exception:
                pass
            try:
                self.db.exam_schedules.update_one({"student_id": old_student_id}, {"$set": {"student_id": new_student_id}})
            except Exception:
                pass

            return True
        except Exception as e:
            print(f"Error migrating student_id in MongoDB: {e}")
            return False

# Global instance
mongo_service = MongoService()
