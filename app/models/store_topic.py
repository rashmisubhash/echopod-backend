from pydantic import BaseModel

CATEGORIES = ["Technical & Programming", "Mathematics and Algorithms", "Science & Engineering", "History & Social Studies", "Creative Writing & Literature", "Health & Medicine"]
DIFFICULTY_LEVELS = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]

# Define request schema
class TopicRequest(BaseModel):
    category: str
    topic: str
    desc: str
    level_of_difficulty: str
    chapters: int
