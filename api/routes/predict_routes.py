from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from core.model import predict_gesture
from models.sensor_models import SensorData
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/predict", tags=["Prediction"])

@router.post("/")
async def predict(sensor_data: SensorData, _user=Depends(role_or_internal_dep("viewer"))):
    """
    Predict gesture from a single sensor data input.
    """
    try:
        # sensor_data.values: list of 11 or 22 floats
        prediction = predict_gesture(sensor_data.values)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "prediction": prediction,
                "session_id": sensor_data.session_id
            }
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.get("/latest-model")
async def get_latest_model_info(_user=Depends(role_or_internal_dep("viewer"))):
    """
    Return info about the latest trained model (timestamp, accuracy, etc.).
    """
    try:
        from core.database import model_collection
        doc = await model_collection.find_one(sort=[("timestamp", -1)])
        if not doc:
            return {"status": "success", "data": None}
        doc["_id"] = str(doc["_id"])
        return {"status": "success", "data": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch model info: {str(e)}")
