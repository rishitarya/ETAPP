from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import traceback
from statement_extraction import statement_extraction

# Import your existing functions
# from your_module import statement_extraction

app = FastAPI(title="Expense Tracker Scheduler API")

# Optional request model
class ExtractionRequest(BaseModel):
    banks: Optional[List[str]] = ['axis', 'axiscc', 'mahb', 'hdfc']
    days: Optional[int] = 7

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}

@app.post("/extract-statements")
def run_extraction(request: ExtractionRequest):
    """
    Trigger statement extraction for given banks and days.
    """
    try:
        result = statement_extraction(banks=request.banks, days=request.days)
        if result == 0:
            return {"status": "success", "message": "Statements pushed to Google Sheets"}
        else:
            return {"status": "failure", "message": "Statement extraction failed"}
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }