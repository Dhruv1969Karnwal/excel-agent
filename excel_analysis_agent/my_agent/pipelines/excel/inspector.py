"""Excel file inspection and metadata extraction."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd


async def load_excel_file(file_path: str) -> pd.DataFrame:
    """
    Load an Excel or CSV file into a pandas DataFrame.
    
    Args:
        file_path: Path to the Excel/CSV file
        
    Returns:
        pandas DataFrame containing the data
        
    Raises:
        ValueError: If the file cannot be loaded
    """
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = await asyncio.to_thread(pd.read_csv, file_path)
        else:
            df = await asyncio.to_thread(pd.read_excel, file_path)
        return df
    except Exception as e:
        raise ValueError(f"Error loading file: {str(e)}")


async def analyze_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze a DataFrame and extract key information.
    
    Args:
        df: pandas DataFrame to analyze
        
    Returns:
        Dictionary containing analysis results
    """
    def _analyze():
        analysis = {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "column_names": df.columns.tolist(),
            "column_types": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
            "missing_values": df.isnull().sum().to_dict(),
            "numeric_columns": df.select_dtypes(include=["number"]).columns.tolist(),
            "categorical_columns": df.select_dtypes(
                include=["object", "category"]
            ).columns.tolist(),
            "sample_rows": df.head(5).to_dict("records"),
        }

        # Add basic statistics for numeric columns
        if analysis["numeric_columns"]:
            analysis["numeric_stats"] = (
                df[analysis["numeric_columns"]].describe().to_dict()
            )

        return analysis

    return await asyncio.to_thread(_analyze)


async def generate_data_description(analysis: Dict[str, Any]) -> str:
    """
    Generate a human-readable description of the Excel data.
    
    Args:
        analysis: Dictionary containing analysis results
        
    Returns:
        Textual description of the data
    """
    description_parts = [
        "Dataset Overview:",
        f"- Total rows: {analysis['num_rows']}",
        f"- Total columns: {analysis['num_columns']}",
        "\nColumn Information:",
        f"- Numeric columns ({len(analysis['numeric_columns'])}): {', '.join(analysis['numeric_columns'])}",
        f"- Categorical columns ({len(analysis['categorical_columns'])}): {', '.join(analysis['categorical_columns'])}",
    ]

    # Add missing value information
    missing = {k: v for k, v in analysis["missing_values"].items() if v > 0}
    if missing:
        description_parts.append("\nMissing Values:")
        for col, count in missing.items():
            description_parts.append(f"- {col}: {count} missing values")
    else:
        description_parts.append("\nNo missing values detected.")

    # Add sample data
    description_parts.append("\nSample Data (first 5 rows):")
    for i, row in enumerate(analysis["sample_rows"], 1):
        description_parts.append(f"Row {i}: {row}")

    # Add numeric statistics if available
    if "numeric_stats" in analysis:
        description_parts.append("\nNumeric Column Statistics:")
        for col in analysis["numeric_columns"]:
            stats = analysis["numeric_stats"][col]
            description_parts.append(
                f"- {col}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, "
                f"min={stats['min']:.2f}, max={stats['max']:.2f}"
            )

    return "\n".join(description_parts)


async def inspect_excel_file(file_path: str) -> Dict[str, Any]:
    """
    Full inspection of an Excel file.
    
    Loads the file, analyzes its structure, and generates a comprehensive
    context for the analysis agent.
    
    Args:
        file_path: Path to the Excel/CSV file
        
    Returns:
        Structured data context for the agent
    """
    df = await load_excel_file(file_path)
    analysis = await analyze_dataframe(df)
    description = await generate_data_description(analysis)
    
    file_name = await asyncio.to_thread(lambda: Path(file_path).name)
    
    return {
        "file_path": os.path.abspath(file_path),
        "file_name": file_name,
        "document_type": "Excel",
        "analyzed_at": datetime.now().isoformat(),
        "description": description,
        "summary": {
            "num_rows": analysis['num_rows'],
            "num_columns": analysis['num_columns'],
            "column_names": analysis['column_names'],
            "numeric_columns": analysis['numeric_columns'],
            "categorical_columns": analysis['categorical_columns'],
        },
        "capabilities": [
            "statistical_analysis",
            "visualization",
            "machine_learning",
            "data_transformation",
            "correlation_analysis",
            "trend_analysis",
        ]
    }
