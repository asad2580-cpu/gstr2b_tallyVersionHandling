import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
import logging
from gstr2b_dedicated_processor import GSTR2BVendor, GSTR2BInvoice

logger = logging.getLogger(__name__)

class GSTR2BTransactionsXMLGenerator:
    """Generate Transactions XML for GSTR2B purchase vouchers to import into Tally."""
    
    def __init__(self, company_name: str, company_state: str):
        """
        Initialize GSTR2B Transactions XML generator.
        
        Args:
            company_name: Name of the company in Tally
            company_state: Company's state for interstate determination
        """
        self.company_name = company_name
        self.company_state = company_state
        
        # State code mapping
        self.state_codes = {
            "07": "Delhi", "01": "Jammu and Kashmir", "02": "Himachal Pradesh",
            "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
            "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
            "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
            "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
            "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
            "24": "Gujarat", "25": "Daman and Diu", "26": "Dadra and Nagar Haveli",
            "27": "Maharashtra", "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa",
            "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
            "35": "Andaman and Nicobar Islands", "36": "Telangana"
        }
    
    def generate_transactions_xml(self, invoices: List[GSTR2BInvoice], metadata: Dict[str, Any]) -> str:
        """
        Generate Transactions XML containing all purchase vouchers.
        
        Args:
            invoices: List of GSTR2BInvoice objects
            metadata: GSTR2B metadata
            
        Returns:
            XML string for Tally import
        """
        try:
            # Create root envelope
            envelope = ET.Element("ENVELOPE")
            
            # Header
            header = ET.SubElement(envelope, "HEADER")
            ET.SubElement(header, "TALLYREQUEST").text = "Import Data"
            ET.SubElement(header, "TYPE").text = "Data"
            ET.SubElement(header, "ID").text = "Vouchers"
            
            # Body
            body = ET.SubElement(envelope, "BODY")
            import_data = ET.SubElement(body, "IMPORTDATA")
            
            # Request description
            request_desc = ET.SubElement(import_data, "REQUESTDESC")
            ET.SubElement(request_desc, "REPORTNAME").text = "Vouchers"
            static_vars = ET.SubElement(request_desc, "STATICVARIABLES")
            ET.SubElement(static_vars, "SVCURRENTCOMPANY").text = self.company_name
            
            # Request data
            request_data = ET.SubElement(import_data, "REQUESTDATA")
            
            # Create purchase vouchers for each invoice
            voucher_number = 1
            for invoice in invoices:
                self._create_purchase_voucher(request_data, invoice, voucher_number)
                voucher_number += 1
            
            return self._prettify_xml(envelope)
            
        except Exception as e:
            logger.error(f"Error generating GSTR2B Transactions XML: {e}")
            return ""
    
    def _create_purchase_voucher(self, parent: ET.Element, invoice: GSTR2BInvoice, voucher_number: int):
        """Create a purchase voucher for an invoice."""
        try:
            msg = ET.SubElement(parent, "TALLYMESSAGE")
            msg.set("xmlns:UDF", "TallyUDF")
            voucher = ET.SubElement(msg, "VOUCHER")
            voucher.set("VCHTYPE", "Purchase")
            voucher.set("ACTION", "Create")
            
            # Voucher header
            ET.SubElement(voucher, "DATE").text = self._format_date_for_tally(invoice.invoice_date)
            ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Purchase"
            ET.SubElement(voucher, "VOUCHERNUMBER").text = f"GSTR2B-{voucher_number:04d}"
            ET.SubElement(voucher, "REFERENCE").text = f"{invoice.invoice_number} ({invoice.vendor_name})"
            ET.SubElement(voucher, "NARRATION").text = f"GSTR2B Purchase from {invoice.vendor_name} - Invoice: {invoice.invoice_number}"
            
            # Determine if interstate
            is_interstate = self._is_interstate_transaction(invoice)
            
            # Vendor ledger entry (Credit side - Sundry Creditor increases)
            vendor_name = self._clean_ledger_name(invoice.vendor_name or f"Vendor-{invoice.vendor_ctin}")
            vendor_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(vendor_entry, "LEDGERNAME").text = vendor_name
            ET.SubElement(vendor_entry, "ISDEEMEDPOSITIVE").text = "Yes"  # Credit
            ET.SubElement(vendor_entry, "AMOUNT").text = f"{invoice.invoice_value:.2f}"
            
            # Add bill details
            if invoice.invoice_number:
                bill_allocations = ET.SubElement(vendor_entry, "BILLALLOCATIONS.LIST")
                ET.SubElement(bill_allocations, "NAME").text = invoice.invoice_number
                ET.SubElement(bill_allocations, "BILLTYPE").text = "New Ref"
                ET.SubElement(bill_allocations, "AMOUNT").text = f"-{invoice.invoice_value:.2f}"
                ET.SubElement(bill_allocations, "BILLDATE").text = self._format_date_for_tally(invoice.invoice_date)
            
            # Purchase ledger entry (Debit side - Expense increases)
            purchase_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(purchase_entry, "LEDGERNAME").text = "Purchase - Trading Goods"
            ET.SubElement(purchase_entry, "ISDEEMEDPOSITIVE").text = "No"  # Debit
            ET.SubElement(purchase_entry, "AMOUNT").text = f"{invoice.taxable_value:.2f}"
            
            # Tax entries (Debit side - Input tax credit is an asset)
            if is_interstate and invoice.igst_amount > 0:
                # IGST for interstate
                igst_rate = self._calculate_tax_rate(invoice.taxable_value, invoice.igst_amount)
                igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(igst_entry, "LEDGERNAME").text = f"Input IGST {igst_rate}%"
                ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "No"  # Debit
                ET.SubElement(igst_entry, "AMOUNT").text = f"{invoice.igst_amount:.2f}"
            else:
                # CGST + SGST for intrastate
                if invoice.cgst_amount > 0:
                    cgst_rate = self._calculate_tax_rate(invoice.taxable_value, invoice.cgst_amount)
                    cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(cgst_entry, "LEDGERNAME").text = f"Input CGST {cgst_rate}%"
                    ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "No"  # Debit
                    ET.SubElement(cgst_entry, "AMOUNT").text = f"{invoice.cgst_amount:.2f}"
                
                if invoice.sgst_amount > 0:
                    sgst_rate = self._calculate_tax_rate(invoice.taxable_value, invoice.sgst_amount)
                    sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(sgst_entry, "LEDGERNAME").text = f"Input SGST {sgst_rate}%"
                    ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "No"  # Debit
                    ET.SubElement(sgst_entry, "AMOUNT").text = f"{invoice.sgst_amount:.2f}"
            
            # CESS if applicable
            if invoice.cess_amount > 0:
                cess_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(cess_entry, "LEDGERNAME").text = "Input CESS"
                ET.SubElement(cess_entry, "ISDEEMEDPOSITIVE").text = "No"  # Debit
                ET.SubElement(cess_entry, "AMOUNT").text = f"{invoice.cess_amount:.2f}"
            
        except Exception as e:
            logger.error(f"Error creating purchase voucher for invoice {invoice.invoice_number}: {e}")
    
    def _is_interstate_transaction(self, invoice: GSTR2BInvoice) -> bool:
        """Determine if transaction is interstate based on GSTIN and POS."""
        try:
            if not invoice.vendor_ctin or len(invoice.vendor_ctin) < 2:
                return False
            
            vendor_state_code = invoice.vendor_ctin[:2]
            # Get company state code from configured state
            company_state_code = self._get_state_code_from_name(self.company_state)
            
            # Check POS (Place of Supply) if available
            if invoice.pos and invoice.pos != company_state_code:
                return True
            
            # Check if vendor state is different from company state
            if vendor_state_code != company_state_code:
                return True
            
            # Also check if IGST is present (clear indicator of interstate)
            return invoice.igst_amount > 0
            
        except Exception as e:
            logger.error(f"Error determining interstate status: {e}")
            return False
    
    def _get_state_code_from_name(self, state_name: str) -> str:
        """Get state code from state name."""
        # Reverse lookup in state_codes dict
        for code, name in self.state_codes.items():
            if name == state_name:
                return code
        return "07"  # Default to Delhi if not found
    
    def _calculate_tax_rate(self, taxable_value: float, tax_amount: float) -> int:
        """Calculate tax rate percentage."""
        if taxable_value <= 0:
            return 0
        
        rate = (tax_amount / taxable_value) * 100
        return round(rate)
    
    def _format_date_for_tally(self, date_str: str) -> str:
        """Format date for Tally (YYYYMMDD)."""
        if not date_str:
            return datetime.now().strftime("%Y%m%d")
        
        try:
            # Input format is YYYY-MM-DD, Tally needs YYYYMMDD
            if '-' in date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.strftime("%Y%m%d")
            else:
                return datetime.now().strftime("%Y%m%d")
        except Exception as e:
            logger.error(f"Error formatting date {date_str}: {e}")
            return datetime.now().strftime("%Y%m%d")
    
    def _clean_ledger_name(self, name: str) -> str:
        """Clean and format ledger name for Tally."""
        if not name:
            return "Unknown Vendor"
        
        # Remove special characters and limit length
        cleaned = ''.join(c for c in name if c.isalnum() or c.isspace() or c in '-._')
        return cleaned[:99].strip()  # Tally has ledger name limits
    
    def _prettify_xml(self, element: ET.Element) -> str:
        """Convert XML element to prettified string."""
        xml_str = ET.tostring(element, encoding='unicode')
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        
        # Basic prettification
        lines = xml_str.split('>')
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('</'):
                indent_level -= 1
            
            formatted_lines.append('  ' * indent_level + line + '>')
            
            if not line.startswith('</') and not line.endswith('/>') and '</' not in line:
                indent_level += 1
        
        formatted_xml = xml_declaration + '\n'.join(formatted_lines)
        return formatted_xml.replace('>>', '>')
    
    def validate_transactions_xml(self, invoices: List[GSTR2BInvoice]) -> Dict[str, Any]:
        """Validate transaction data before XML generation."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if not invoices:
            validation_result['valid'] = False
            validation_result['errors'].append("No invoices found for Transactions XML generation")
            return validation_result
        
        # Check for missing invoice numbers
        invoices_without_number = [inv for inv in invoices if not inv.invoice_number]
        if invoices_without_number:
            validation_result['warnings'].append(f"{len(invoices_without_number)} invoices without invoice number")
        
        # Check for zero value invoices
        zero_value_invoices = [inv for inv in invoices if inv.invoice_value <= 0]
        if zero_value_invoices:
            validation_result['warnings'].append(f"{len(zero_value_invoices)} invoices with zero or negative value")
        
        # Check tax calculation consistency
        inconsistent_invoices = []
        for inv in invoices:
            calculated_total = inv.taxable_value + inv.cgst_amount + inv.sgst_amount + inv.igst_amount + inv.cess_amount
            if abs(calculated_total - inv.invoice_value) > 0.01:  # Allow 1 paisa difference
                inconsistent_invoices.append(inv.invoice_number)
        
        if inconsistent_invoices:
            validation_result['warnings'].append(f"Tax calculation inconsistencies in invoices: {inconsistent_invoices[:5]}")
        
        # Summary
        total_value = sum(inv.invoice_value for inv in invoices)
        total_tax = sum(inv.cgst_amount + inv.sgst_amount + inv.igst_amount + inv.cess_amount for inv in invoices)
        interstate_count = len([inv for inv in invoices if self._is_interstate_transaction(inv)])
        
        validation_result['summary'] = {
            'total_invoices': len(invoices),
            'total_invoice_value': total_value,
            'total_tax_amount': total_tax,
            'interstate_invoices': interstate_count,
            'intrastate_invoices': len(invoices) - interstate_count
        }
        
        return validation_result
