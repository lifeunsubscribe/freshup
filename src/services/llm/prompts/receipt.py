"""
Prompt templates for receipt parsing.

Defines system and user prompts for Ollama-based receipt text parsing.
Instructs the LLM to extract structured data from raw OCR text.

Per ADR Phase 4B: Receipt parsing uses Tesseract OCR for initial text extraction,
then Ollama LLM for intelligent parsing into structured line items.
"""

# System prompt: Instructs LLM to return ONLY valid JSON with no preamble
SYSTEM_PROMPT = """You are a receipt parsing assistant. Your job is to extract structured data from grocery receipt text.

You must return ONLY valid JSON matching the required schema. Do not include any preamble, explanation, markdown formatting, or additional text. Return ONLY the JSON object.

The JSON schema you must follow:
{
  "store_name": "string (required) - Name of the store",
  "receipt_date": "string in YYYY-MM-DD format (or null if illegible/missing)",
  "line_items": [
    {
      "item_name": "string (required) - Product name",
      "quantity": number or null - Quantity purchased,
      "unit_price": number or null - Price per unit,
      "total_price": number or null - Total line item price,
      "category_guess": "string or null - Your best guess at the grocery category"
    }
  ]
}

Guidelines:
- store_name: Extract the store name from the header (e.g., "Costco", "King Soopers", "Save-A-Lot")
- receipt_date: Parse date into YYYY-MM-DD format. If illegible or missing, use null
- item_name: Clean and normalize product names (remove extra spaces, fix obvious OCR errors)
- quantity: Extract if visible. If not specified, use null
- unit_price: Extract if visible (price per pound, per unit, etc.). If not specified, use null
- total_price: Extract the line item total price. If not visible, use null
- category_guess: Classify into common grocery categories:
  - "produce" - fruits, vegetables
  - "protein" - meat, poultry, seafood, eggs
  - "dairy" - milk, cheese, yogurt
  - "grain" - bread, pasta, rice, cereal
  - "pantry_staple" - oil, flour, sugar, spices, canned goods
  - "frozen" - frozen meals, ice cream
  - "snack" - chips, cookies, candy
  - "condiment" - sauces, dressings, spreads
  - "beverage" - drinks (non-dairy)
  - Use null if you cannot confidently categorize

Handle OCR errors gracefully:
- "M1LK" → "Milk"
- "0RANGES" → "Oranges"
- "CHlCKEN" (lowercase L instead of I) → "Chicken"

Return ONLY the JSON. No markdown, no explanations."""


# User prompt template: Accepts raw receipt text for parsing
USER_PROMPT_TEMPLATE = """Parse the following grocery receipt text into structured JSON:

{receipt_text}

Remember: Return ONLY valid JSON with no additional text or formatting."""


def create_user_prompt(receipt_text: str) -> str:
    """
    Create a user prompt for receipt parsing.

    Args:
        receipt_text: Raw text extracted from receipt (from OCR or digital source)

    Returns:
        Formatted prompt ready to send to LLM
    """
    return USER_PROMPT_TEMPLATE.format(receipt_text=receipt_text)
