from fastapi import APIRouter
from app.services.store_topic import store_topic_lambda
from app.models.store_topic import TopicRequest

# Initialize FastAPI Router
router = APIRouter()

@router.post("/store-topic")
def store_topic(request: TopicRequest):
    """sumary_line
    
    Keyword arguments:
    argument -- description
    Return: return_description
    """
    return store_topic_lambda(request)




    
    


