#!/usr/bin/env python3
"""Test script to check profile creation and retrieval"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.exam_service import exam_service
from app.services.mongo_service import mongo_service

def test_profile_creation():
    print("=== Testing Profile Creation ===")

    # Test data
    test_student = {
        "student_id": "TEST123",
        "name": "Test Student",
        "email": "test@example.com",
        "project_title": "Test Project",
        "project_description": "Test Description",
        "technologies": ["Python", "React"],
        "metrics": ["Accuracy: 95%"],
        "case_study": "Test case study"
    }

    print(f"Before creation - students in memory: {list(exam_service.students.keys())}")
    print(f"MongoDB connected: {mongo_service.is_connected()}")

    # Create profile
    exam_service.register_student(test_student)

    print(f"After creation - students in memory: {list(exam_service.students.keys())}")
    print(f"Student data in memory: {exam_service.students.get('TEST123')}")

    # Test retrieval
    found_student = None
    for sid, data in exam_service.students.items():
        if data.get("email") == "test@example.com":
            found_student = data
            break

    print(f"Found student by email: {found_student is not None}")
    if found_student:
        print(f"Student data: {found_student}")

if __name__ == "__main__":
    test_profile_creation()