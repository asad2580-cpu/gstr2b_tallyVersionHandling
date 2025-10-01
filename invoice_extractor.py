import json
import logging
import os
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InvoiceItem(BaseModel):
    description: str
    hsn_code: Optional[str] = None
    quantity: float
    unit: str
    rate: float
    taxable_value: float
    cgst_rate: Optional[float] = None
    cgst_amount: Optional[float] = None
    sgst_rate: Optional[float] = None
    sgst_amount: Optional[float] = None
    igst_rate: Optional[float] = None
    igst_amount: Optional[float] = None
    total_amount: float

class Invoice(BaseModel):
    invoice_number: str
    invoice_date: str
    vendor_name: str
    vendor_gstin: Optional[str] = None
    vendor_address: str
    vendor_state: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_gstin: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_state: Optional[str] = None
    total_taxable_value: float
    total_cgst: Optional[float] = None
    total_sgst: Optional[float] = None
    total_igst: Optional[float] = None
    total_tax_amount: float
    total_invoice_value: float
    items: List[InvoiceItem]
    invoice_type: str  # 'purchase' or 'sales'

class InvoiceExtractor:
    def __init__(self):
        """Initialize the invoice extractor with Gemini client."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=api_key)
    
    def extract_invoice_data(self, image_bytes: bytes, invoice_type: str, company_state: str) -> Dict[str, Any]:
        """
        Extract invoice data from image.
        
        Args:
            image_bytes: Image data as bytes
            invoice_type: 'purchase' or 'sales'
            company_state: Company's state for GST calculation
            
        Returns:
            Invoice data dictionary
        """
        try:
            # Create prompt based on invoice type
            if invoice_type.lower() == 'purchase':
                prompt = self._get_purchase_invoice_prompt(company_state)
            else:
                prompt = self._get_sales_invoice_prompt(company_state)
            
            # Optimize image before processing
            optimized_image_bytes = self._optimize_image(image_bytes)
            
            # Generate content with image analysis
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(
                        data=optimized_image_bytes,
                        mime_type="image/png",
                    ),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            if not response.text:
                logger.error("Empty response from Gemini API")
                return {}

            # Parse JSON response with validation
            try:
                invoice_data = json.loads(response.text)
                
                # Validate basic structure
                if not isinstance(invoice_data, dict):
                    logger.error("Response is not a valid dictionary")
                    return {}
                
                # Ensure required fields exist
                required_fields = ['invoice_number', 'invoice_date', 'total_invoice_value']
                for field in required_fields:
                    if field not in invoice_data:
                        logger.warning(f"Missing required field: {field}")
                
                # Ensure items is a list
                if 'items' not in invoice_data or not isinstance(invoice_data['items'], list):
                    invoice_data['items'] = []
                
                logger.info(f"Successfully extracted invoice data with {len(invoice_data.get('items', []))} items")
                
                # Add invoice type to the data
                invoice_data['invoice_type'] = invoice_type.lower()
                
                return invoice_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {response.text}")
                return {}
            except Exception as e:
                logger.error(f"Error processing invoice data: {e}")
                return {}

        except Exception as e:
            logger.error(f"Error extracting invoice data: {e}")
            return {}
    
    def _get_purchase_invoice_prompt(self, company_state: str) -> str:
        """Get prompt for purchase invoice extraction."""
        return f"""Extract all information from this purchase invoice as JSON.

Company state: {company_state}

Required fields:
- invoice_number: Invoice/Bill number
- invoice_date: Date (YYYY-MM-DD format)
- vendor_name: Supplier/Vendor name
- vendor_gstin: Vendor GST number (if available)
- vendor_address: Vendor address
- vendor_state: Vendor state name (if identifiable)
- total_taxable_value: Total taxable amount before tax
- total_cgst: Total CGST amount (if intrastate)
- total_sgst: Total SGST amount (if intrastate)
- total_igst: Total IGST amount (if interstate)
- total_tax_amount: Total tax amount
- total_invoice_value: Final invoice amount
- items: Array of line items with:
  - description: Item description
  - hsn_code: HSN/SAC code (if available)
  - quantity: Quantity
  - unit: Unit of measurement
  - rate: Rate per unit
  - taxable_value: Taxable amount for this item
  - cgst_rate: CGST rate % (if intrastate)
  - cgst_amount: CGST amount (if intrastate)
  - sgst_rate: SGST rate % (if intrastate)
  - sgst_amount: SGST amount (if intrastate)
  - igst_rate: IGST rate % (if interstate)
  - igst_amount: IGST amount (if interstate)
  - total_amount: Total amount for this item

Important: 
- If vendor state is same as {company_state}, use CGST+SGST
- If vendor state is different from {company_state}, use IGST
- Return only valid JSON"""

    def _get_sales_invoice_prompt(self, company_state: str) -> str:
        """Get prompt for sales invoice extraction."""
        return f"""Extract all information from this sales invoice as JSON.

Company state: {company_state}

Required fields:
- invoice_number: Invoice number
- invoice_date: Date (YYYY-MM-DD format)
- buyer_name: Customer/Buyer name
- buyer_gstin: Buyer GST number (if available)
- buyer_address: Buyer address
- buyer_state: Buyer state name (if identifiable)
- total_taxable_value: Total taxable amount before tax
- total_cgst: Total CGST amount (if intrastate)
- total_sgst: Total SGST amount (if intrastate)
- total_igst: Total IGST amount (if interstate)
- total_tax_amount: Total tax amount
- total_invoice_value: Final invoice amount
- items: Array of line items with:
  - description: Item description
  - hsn_code: HSN/SAC code (if available)
  - quantity: Quantity
  - unit: Unit of measurement
  - rate: Rate per unit
  - taxable_value: Taxable amount for this item
  - cgst_rate: CGST rate % (if intrastate)
  - cgst_amount: CGST amount (if intrastate)
  - sgst_rate: SGST rate % (if intrastate)
  - sgst_amount: SGST amount (if intrastate)
  - igst_rate: IGST rate % (if interstate)
  - igst_amount: IGST amount (if interstate)
  - total_amount: Total amount for this item

Important: 
- If buyer state is same as {company_state}, use CGST+SGST
- If buyer state is different from {company_state}, use IGST
- Return only valid JSON"""
    
    def _optimize_image(self, image_bytes: bytes) -> bytes:
        """Optimize image for processing."""
        try:
            # Open image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large (max 2048x2048)
            max_size = 2048
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save as PNG with optimization
            output = io.BytesIO()
            image.save(output, format='PNG', optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.warning(f"Image optimization failed: {e}, using original")
            return image_bytes