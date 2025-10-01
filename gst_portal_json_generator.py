import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GSTPortalJSONGenerator:
    """Generate GST portal compatible JSON files for offline filing."""
    
    def __init__(self, company_gstin: str, company_state: str):
        """
        Initialize GST portal JSON generator.
        
        Args:
            company_gstin: Company's GSTIN
            company_state: Company's state
        """
        self.company_gstin = company_gstin
        self.company_state = company_state
        
        # State code mapping
        self.state_codes = {
            "Andhra Pradesh": "37", "Arunachal Pradesh": "12", "Assam": "18", "Bihar": "10",
            "Chhattisgarh": "22", "Goa": "30", "Gujarat": "24", "Haryana": "06", 
            "Himachal Pradesh": "02", "Jharkhand": "20", "Karnataka": "29", "Kerala": "32",
            "Madhya Pradesh": "23", "Maharashtra": "27", "Manipur": "14", "Meghalaya": "17",
            "Mizoram": "15", "Nagaland": "13", "Odisha": "21", "Punjab": "03", "Rajasthan": "08",
            "Sikkim": "11", "Tamil Nadu": "33", "Telangana": "36", "Tripura": "16",
            "Uttar Pradesh": "09", "Uttarakhand": "05", "West Bengal": "19", "Delhi": "07",
            "Puducherry": "34"
        }
    
    def generate_gstr1_json(self, sales_invoices: List[Dict[str, Any]], month: str, year: str) -> Dict[str, Any]:
        """
        Generate GSTR1 JSON for sales invoices.
        
        Args:
            sales_invoices: List of sales invoice data
            month: Month (MM format)
            year: Year (YYYY format)
            
        Returns:
            GSTR1 JSON structure
        """
        try:
            # Initialize GSTR1 structure
            gstr1_data = {
                "gstin": self.company_gstin,
                "ret_period": f"{month}{year}",
                "version": "GST3.0.4",
                "hash": "hash",
                "b2b": [],
                "b2cl": [],
                "b2cs": [],
                "hsn": {},
                "doc_issue": []
            }
            
            # Process each invoice
            for invoice in sales_invoices:
                buyer_gstin = invoice.get('buyer_gstin', '').strip()
                total_value = float(invoice.get('total_invoice_value', 0))
                buyer_state = invoice.get('buyer_state', '').strip()
                
                # Determine invoice category
                if buyer_gstin and len(buyer_gstin) == 15:
                    # B2B - Business to Business (with GSTIN)
                    self._add_b2b_invoice(gstr1_data, invoice)
                elif total_value > 250000 and not buyer_gstin:
                    # B2CL - Business to Consumer Large (>2.5L without GSTIN)
                    self._add_b2cl_invoice(gstr1_data, invoice)
                else:
                    # B2CS - Business to Consumer Small (<=2.5L without GSTIN)
                    self._add_b2cs_invoice(gstr1_data, invoice)
                
                # Add HSN summary
                self._add_hsn_summary(gstr1_data, invoice)
            
            # Process HSN summary
            gstr1_data["hsn"] = self._process_hsn_summary(gstr1_data["hsn"])
            
            return gstr1_data
            
        except Exception as e:
            logger.error(f"Error generating GSTR1 JSON: {e}")
            return {}
    
    def _add_b2b_invoice(self, gstr1_data: Dict[str, Any], invoice: Dict[str, Any]):
        """Add B2B invoice to GSTR1."""
        buyer_gstin = invoice.get('buyer_gstin', '').strip()
        
        # Find existing GSTIN entry or create new
        gstin_entry = None
        for entry in gstr1_data["b2b"]:
            if entry["ctin"] == buyer_gstin:
                gstin_entry = entry
                break
        
        if not gstin_entry:
            gstin_entry = {
                "ctin": buyer_gstin,
                "inv": []
            }
            gstr1_data["b2b"].append(gstin_entry)
        
        # Create invoice entry
        invoice_entry = {
            "inum": invoice.get('invoice_number', ''),
            "idt": self._format_date_for_gst(invoice.get('invoice_date', '')),
            "val": float(invoice.get('total_invoice_value', 0)),
            "pos": self._get_state_code(invoice.get('buyer_state', '')),
            "rchrg": "N",
            "inv_typ": "R",
            "itms": []
        }
        
        # Add items
        for item in invoice.get('items', []):
            item_entry = {
                "num": len(invoice_entry["itms"]) + 1,
                "itm_det": {
                    "hsn_sc": item.get('hsn_code', ''),
                    "txval": float(item.get('taxable_value', 0)),
                    "rt": float(item.get('igst_rate', 0)) if item.get('igst_amount', 0) > 0 else float(item.get('cgst_rate', 0)) * 2,
                    "iamt": float(item.get('igst_amount', 0)),
                    "camt": float(item.get('cgst_amount', 0)),
                    "samt": float(item.get('sgst_amount', 0)),
                    "csamt": 0
                }
            }
            invoice_entry["itms"].append(item_entry)
        
        gstin_entry["inv"].append(invoice_entry)
    
    def _add_b2cl_invoice(self, gstr1_data: Dict[str, Any], invoice: Dict[str, Any]):
        """Add B2CL invoice to GSTR1."""
        invoice_entry = {
            "inum": invoice.get('invoice_number', ''),
            "idt": self._format_date_for_gst(invoice.get('invoice_date', '')),
            "val": float(invoice.get('total_invoice_value', 0)),
            "pos": self._get_state_code(invoice.get('buyer_state', '')),
            "itms": []
        }
        
        # Add items
        for item in invoice.get('items', []):
            item_entry = {
                "num": len(invoice_entry["itms"]) + 1,
                "itm_det": {
                    "hsn_sc": item.get('hsn_code', ''),
                    "txval": float(item.get('taxable_value', 0)),
                    "rt": float(item.get('igst_rate', 0)) if item.get('igst_amount', 0) > 0 else float(item.get('cgst_rate', 0)) * 2,
                    "iamt": float(item.get('igst_amount', 0)),
                    "camt": float(item.get('cgst_amount', 0)),
                    "samt": float(item.get('sgst_amount', 0)),
                    "csamt": 0
                }
            }
            invoice_entry["itms"].append(item_entry)
        
        gstr1_data["b2cl"].append(invoice_entry)
    
    def _add_b2cs_invoice(self, gstr1_data: Dict[str, Any], invoice: Dict[str, Any]):
        """Add B2CS invoice to GSTR1."""
        # B2CS is summarized by HSN, rate, and place of supply
        for item in invoice.get('items', []):
            pos = self._get_state_code(invoice.get('buyer_state', ''))
            hsn_code = item.get('hsn_code', '')
            rate = float(item.get('igst_rate', 0)) if item.get('igst_amount', 0) > 0 else float(item.get('cgst_rate', 0)) * 2
            
            # Find existing entry or create new
            entry_key = f"{hsn_code}_{rate}_{pos}"
            entry_found = False
            
            for entry in gstr1_data["b2cs"]:
                if (entry.get("hsn_sc") == hsn_code and 
                    entry.get("rt") == rate and 
                    entry.get("pos") == pos):
                    # Add to existing entry
                    entry["txval"] += float(item.get('taxable_value', 0))
                    entry["iamt"] += float(item.get('igst_amount', 0))
                    entry["camt"] += float(item.get('cgst_amount', 0))
                    entry["samt"] += float(item.get('sgst_amount', 0))
                    entry_found = True
                    break
            
            if not entry_found:
                new_entry = {
                    "hsn_sc": hsn_code,
                    "txval": float(item.get('taxable_value', 0)),
                    "rt": rate,
                    "iamt": float(item.get('igst_amount', 0)),
                    "camt": float(item.get('cgst_amount', 0)),
                    "samt": float(item.get('sgst_amount', 0)),
                    "csamt": 0,
                    "pos": pos,
                    "typ": "OE"
                }
                gstr1_data["b2cs"].append(new_entry)
    
    def _add_hsn_summary(self, gstr1_data: Dict[str, Any], invoice: Dict[str, Any]):
        """Add HSN summary data."""
        if "hsn" not in gstr1_data:
            gstr1_data["hsn"] = {}
        
        for item in invoice.get('items', []):
            hsn_code = item.get('hsn_code', '')
            if not hsn_code:
                continue
            
            if hsn_code not in gstr1_data["hsn"]:
                gstr1_data["hsn"][hsn_code] = {
                    "hsn_sc": hsn_code,
                    "desc": item.get('description', ''),
                    "uqc": item.get('unit', 'NOS'),
                    "qty": 0,
                    "val": 0,
                    "txval": 0,
                    "iamt": 0,
                    "camt": 0,
                    "samt": 0,
                    "csamt": 0
                }
            
            # Accumulate values
            hsn_entry = gstr1_data["hsn"][hsn_code]
            hsn_entry["qty"] += float(item.get('quantity', 0))
            hsn_entry["val"] += float(item.get('total_amount', 0))
            hsn_entry["txval"] += float(item.get('taxable_value', 0))
            hsn_entry["iamt"] += float(item.get('igst_amount', 0))
            hsn_entry["camt"] += float(item.get('cgst_amount', 0))
            hsn_entry["samt"] += float(item.get('sgst_amount', 0))
    
    def _process_hsn_summary(self, hsn_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Process HSN summary into final format."""
        if not hsn_dict:
            return {"data": []}
        
        hsn_list = []
        for hsn_code, hsn_data in hsn_dict.items():
            hsn_list.append({
                "num": len(hsn_list) + 1,
                "hsn_sc": hsn_data["hsn_sc"],
                "desc": hsn_data["desc"][:30],  # Limit description length
                "uqc": hsn_data["uqc"],
                "qty": round(hsn_data["qty"], 2),
                "val": round(hsn_data["val"], 2),
                "txval": round(hsn_data["txval"], 2),
                "iamt": round(hsn_data["iamt"], 2),
                "camt": round(hsn_data["camt"], 2),
                "samt": round(hsn_data["samt"], 2),
                "csamt": round(hsn_data["csamt"], 2)
            })
        
        return {"data": hsn_list}
    
    def _get_state_code(self, state_name: str) -> str:
        """Get state code for GST portal."""
        if not state_name:
            return self.state_codes.get(self.company_state, "01")
        
        # Clean state name
        clean_state = state_name.strip().title()
        return self.state_codes.get(clean_state, "01")
    
    def _format_date_for_gst(self, date_str: str) -> str:
        """Format date for GST portal (DD-MM-YYYY)."""
        if not date_str:
            return datetime.now().strftime("%d-%m-%Y")
        
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%d-%m-%Y")
                except ValueError:
                    continue
            
            logger.warning(f"Could not parse date: {date_str}, using current date")
            return datetime.now().strftime("%d-%m-%Y")
            
        except Exception as e:
            logger.error(f"Error formatting date {date_str}: {e}")
            return datetime.now().strftime("%d-%m-%Y")
    
    def validate_gstr1_data(self, gstr1_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GSTR1 data before generation."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check required fields
        if not gstr1_data.get('gstin'):
            validation_result['valid'] = False
            validation_result['errors'].append("GSTIN is required")
        
        if not gstr1_data.get('ret_period'):
            validation_result['valid'] = False
            validation_result['errors'].append("Return period is required")
        
        # Validate invoice data
        total_invoices = len(gstr1_data.get('b2b', [])) + len(gstr1_data.get('b2cl', [])) + len(gstr1_data.get('b2cs', []))
        if total_invoices == 0:
            validation_result['warnings'].append("No invoices found in the return")
        
        # Validate HSN data
        hsn_data = gstr1_data.get('hsn', {}).get('data', [])
        if not hsn_data:
            validation_result['warnings'].append("No HSN summary data found")
        
        return validation_result