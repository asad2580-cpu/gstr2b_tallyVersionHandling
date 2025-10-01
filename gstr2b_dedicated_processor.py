import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GSTR2BVendor:
    """Represents a vendor from GSTR2B data."""
    ctin: str
    trdnm: str
    total_invoices: int
    total_taxable_value: float
    total_cgst: float
    total_sgst: float
    total_igst: float
    total_cess: float
    invoices: List[Dict[str, Any]]

@dataclass 
class GSTR2BInvoice:
    """Represents an invoice from GSTR2B data."""
    vendor_ctin: str
    vendor_name: str
    invoice_number: str
    invoice_date: str
    invoice_value: float
    taxable_value: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    cess_amount: float
    itc_available: str
    reverse_charge: str
    pos: str

class GSTR2BDedicatedProcessor:
    """Dedicated processor for official GSTR2B JSON files from GST portal."""
    
    def __init__(self, company_state: str):
        """Initialize GSTR2B processor."""
        self.company_state = company_state
        
        # State code mapping for interstate determination
        self.state_codes = {
            "Andhra Pradesh": "28", "Arunachal Pradesh": "12", "Assam": "18", "Bihar": "10",
            "Chhattisgarh": "22", "Goa": "30", "Gujarat": "24", "Haryana": "06", 
            "Himachal Pradesh": "02", "Jharkhand": "20", "Karnataka": "29", "Kerala": "32",
            "Madhya Pradesh": "23", "Maharashtra": "27", "Manipur": "14", "Meghalaya": "17",
            "Mizoram": "15", "Nagaland": "13", "Odisha": "21", "Punjab": "03", "Rajasthan": "08",
            "Sikkim": "11", "Tamil Nadu": "33", "Telangana": "36", "Tripura": "16",
            "Uttar Pradesh": "09", "Uttarakhand": "05", "West Bengal": "19", "Delhi": "07",
            "Puducherry": "34", "Andaman and Nicobar Islands": "35", "Chandigarh": "04",
            "Dadra and Nagar Haveli": "26", "Daman and Diu": "25", "Jammu and Kashmir": "01",
            "Ladakh": "02", "Lakshadweep": "31"
        }
    
    def process_gstr2b_json(self, gstr2b_json: Dict[str, Any]) -> Tuple[List[GSTR2BVendor], List[GSTR2BInvoice], Dict[str, Any]]:
        """
        Process official GSTR2B JSON and extract vendors and invoices.
        
        Args:
            gstr2b_json: Official GSTR2B JSON from GST portal
            
        Returns:
            Tuple of (vendors_list, invoices_list, metadata)
        """
        try:
            # Extract metadata
            data = gstr2b_json.get('data', {})
            metadata = {
                'gstin': data.get('gstin', ''),
                'return_period': data.get('rtnprd', ''),
                'generated_date': data.get('gendt', ''),
                'version': data.get('version', ''),
                'checksum': gstr2b_json.get('chksum', '')
            }
            
            logger.info(f"Processing GSTR2B for GSTIN: {metadata['gstin']}, Period: {metadata['return_period']}")
            
            # Process B2B invoices from docdata
            vendors = []
            all_invoices = []
            
            docdata = data.get('docdata', {})
            b2b_data = docdata.get('b2b', [])
            
            for vendor_data in b2b_data:
                vendor = self._process_vendor(vendor_data)
                vendors.append(vendor)
                
                # Process each invoice for this vendor
                for invoice_data in vendor_data.get('inv', []):
                    invoice = self._process_invoice(vendor_data, invoice_data)
                    all_invoices.append(invoice)
            
            logger.info(f"Processed {len(vendors)} vendors with {len(all_invoices)} total invoices")
            return vendors, all_invoices, metadata
            
        except Exception as e:
            logger.error(f"Error processing GSTR2B JSON: {e}")
            return [], [], {}
    
    def _process_vendor(self, vendor_data: Dict[str, Any]) -> GSTR2BVendor:
        """Process vendor data from GSTR2B."""
        ctin = vendor_data.get('ctin', '')
        trdnm = vendor_data.get('trdnm', '')
        invoices = vendor_data.get('inv', [])
        
        # Calculate totals from invoices
        total_taxable = sum(float(inv.get('txval', 0)) for inv in invoices)
        total_cgst = sum(float(inv.get('cgst', 0)) for inv in invoices)
        total_sgst = sum(float(inv.get('sgst', 0)) for inv in invoices)
        total_igst = sum(float(inv.get('igst', 0)) for inv in invoices)
        total_cess = sum(float(inv.get('cess', 0)) for inv in invoices)
        
        return GSTR2BVendor(
            ctin=ctin,
            trdnm=trdnm,
            total_invoices=len(invoices),
            total_taxable_value=total_taxable,
            total_cgst=total_cgst,
            total_sgst=total_sgst,
            total_igst=total_igst,
            total_cess=total_cess,
            invoices=invoices
        )
    
    def _process_invoice(self, vendor_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> GSTR2BInvoice:
        """Process individual invoice data."""
        vendor_ctin = vendor_data.get('ctin', '')
        vendor_name = vendor_data.get('trdnm', '')
        
        return GSTR2BInvoice(
            vendor_ctin=vendor_ctin,
            vendor_name=vendor_name,
            invoice_number=invoice_data.get('inum', ''),
            invoice_date=self._format_date(invoice_data.get('dt', '')),
            invoice_value=float(invoice_data.get('val', 0)),
            taxable_value=float(invoice_data.get('txval', 0)),
            cgst_amount=float(invoice_data.get('cgst', 0)),
            sgst_amount=float(invoice_data.get('sgst', 0)),
            igst_amount=float(invoice_data.get('igst', 0)),
            cess_amount=float(invoice_data.get('cess', 0)),
            itc_available=invoice_data.get('itcavl', 'Y'),
            reverse_charge=invoice_data.get('rev', 'N'),
            pos=invoice_data.get('pos', '')
        )
    
    def _format_date(self, date_str: str) -> str:
        """Format GST date string."""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        
        try:
            # GSTR2B dates are in DD-MM-YYYY format
            if '-' in date_str and len(date_str.split('-')) == 3:
                day, month, year = date_str.split('-')
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime("%Y-%m-%d")
            else:
                return datetime.now().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"Error formatting date {date_str}: {e}")
            return datetime.now().strftime("%Y-%m-%d")
    
    def get_vendor_summary(self, vendors: List[GSTR2BVendor]) -> Dict[str, Any]:
        """Get summary statistics for vendors."""
        if not vendors:
            return {}
        
        total_vendors = len(vendors)
        total_invoices = sum(v.total_invoices for v in vendors)
        total_taxable_value = sum(v.total_taxable_value for v in vendors)
        total_tax_amount = sum(v.total_cgst + v.total_sgst + v.total_igst for v in vendors)
        
        return {
            'total_vendors': total_vendors,
            'total_invoices': total_invoices,
            'total_taxable_value': total_taxable_value,
            'total_tax_amount': total_tax_amount,
            'total_invoice_value': total_taxable_value + total_tax_amount
        }
    
    def validate_gstr2b_data(self, gstr2b_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GSTR2B JSON structure."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check basic structure
        if 'data' not in gstr2b_json:
            validation_result['valid'] = False
            validation_result['errors'].append("Missing 'data' section in GSTR2B JSON")
            return validation_result
        
        data = gstr2b_json['data']
        
        # Check required fields
        required_fields = ['gstin', 'rtnprd', 'docdata']
        for field in required_fields:
            if field not in data:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Missing required field: {field}")
        
        # Check docdata structure
        if 'docdata' in data:
            docdata = data['docdata']
            if 'b2b' not in docdata:
                validation_result['warnings'].append("No B2B data found in docdata")
            elif not docdata['b2b']:
                validation_result['warnings'].append("Empty B2B data found")
        
        # Check for invoices
        total_invoices = 0
        if 'docdata' in data and 'b2b' in data['docdata']:
            for vendor in data['docdata']['b2b']:
                total_invoices += len(vendor.get('inv', []))
        
        if total_invoices == 0:
            validation_result['warnings'].append("No invoices found in GSTR2B data")
        else:
            validation_result['warnings'].append(f"Found {total_invoices} invoices for processing")
        
        return validation_result