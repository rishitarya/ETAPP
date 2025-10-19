from pydantic import BaseModel
from typing import List, Optional
import traceback
from statement_extraction import statement_extraction

def run_extraction(banks = ['axis','axiscc','hdfc','mahb'],days = 7):
    """
    Trigger statement extraction for given banks and days.
    """
    try:
        result = statement_extraction(banks, days)
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
    
if __name__ == "__main__":
    print(run_extraction())