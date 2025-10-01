import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GSTTallyXMLGenerator:
    """Generate Tally XML from GST portal JSON data."""
    
    def __init__(self, company_name: str, company_state: str):
        """
        Initialize GST Tally XML generator.
        
        Args:
            company_name: Name of the company in Tally
            company_state: Company's state
        """
        self.company_name = company_name
        self.company_state = company_state
    
    def generate_gstr2b_xml(self, gstr2b_data: Dict[str, Any]) -> str:
        """Generate Tally XML for GSTR2B (Purchase) data."""
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
        
        # Process B2B invoices
        voucher_number = 1
        if 'itc_avl' in gstr2b_data and 'b2b' in gstr2b_data['itc_avl']:
            for vendor in gstr2b_data['itc_avl']['b2b']:
                vendor_gstin = vendor.get('ctin', '')
                
                # Create vendor ledger
                self._create_vendor_ledger(request_data, vendor_gstin)
                
                for invoice in vendor.get('inv', []):
                    self._add_purchase_voucher_from_gst(request_data, vendor_gstin, invoice, voucher_number)
                    voucher_number += 1
        
        return self._prettify_xml(envelope)
    
    def generate_gstr2a_xml(self, gstr2a_data: Dict[str, Any]) -> str:
        """Generate Tally XML for GSTR2A (Purchase) data."""
        # Similar to GSTR2B but with different structure
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
        
        # Process B2B invoices
        voucher_number = 1
        if 'b2b' in gstr2a_data:
            for vendor in gstr2a_data['b2b']:
                vendor_gstin = vendor.get('ctin', '')
                
                # Create vendor ledger
                self._create_vendor_ledger(request_data, vendor_gstin)
                
                for invoice in vendor.get('inv', []):
                    self._add_purchase_voucher_from_gst(request_data, vendor_gstin, invoice, voucher_number)
                    voucher_number += 1
        
        return self._prettify_xml(envelope)
    
    def generate_gstr1_xml(self, gstr1_data: Dict[str, Any]) -> str:
        """Generate Tally XML for GSTR1 (Sales) data."""
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
        
        # Process B2B invoices
        voucher_number = 1
        if 'b2b' in gstr1_data:
            for customer in gstr1_data['b2b']:
                customer_gstin = customer.get('ctin', '')
                
                # Create customer ledger
                self._create_customer_ledger(request_data, customer_gstin)
                
                for invoice in customer.get('inv', []):
                    self._add_sales_voucher_from_gst(request_data, customer_gstin, invoice, voucher_number)
                    voucher_number += 1
        
        # Process B2CL invoices
        if 'b2cl' in gstr1_data:
            for invoice in gstr1_data['b2cl']:
                self._add_b2cl_sales_voucher(request_data, invoice, voucher_number)
                voucher_number += 1
        
        return self._prettify_xml(envelope)
    
    def _create_vendor_ledger(self, parent: ET.Element, vendor_gstin: str):
        """Create vendor ledger."""
        vendor_name = f"Vendor - {vendor_gstin}"
        
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        ledger = ET.SubElement(msg, "LEDGER")
        ledger.set("NAME", vendor_name)
        ledger.set("ACTION", "Create")
        ET.SubElement(ledger, "PARENT").text = "Sundry Creditors"
        ET.SubElement(ledger, "ISBILLWISEON").text = "Yes"
        
        # Add GSTIN details
        if vendor_gstin:
            ET.SubElement(ledger, "PARTYGSTIN").text = vendor_gstin
    
    def _create_customer_ledger(self, parent: ET.Element, customer_gstin: str):
        """Create customer ledger."""
        customer_name = f"Customer - {customer_gstin}"
        
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        ledger = ET.SubElement(msg, "LEDGER")
        ledger.set("NAME", customer_name)
        ledger.set("ACTION", "Create")
        ET.SubElement(ledger, "PARENT").text = "Sundry Debtors"
        ET.SubElement(ledger, "ISBILLWISEON").text = "Yes"
        
        # Add GSTIN details
        if customer_gstin:
            ET.SubElement(ledger, "PARTYGSTIN").text = customer_gstin
    
    def _add_purchase_voucher_from_gst(self, parent: ET.Element, vendor_gstin: str, invoice: Dict[str, Any], voucher_number: int):
        """Add purchase voucher from GST data."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        voucher = ET.SubElement(msg, "VOUCHER")
        voucher.set("VCHTYPE", "Purchase")
        voucher.set("ACTION", "Create")
        
        # Voucher details
        invoice_date = self._format_gst_date(invoice.get('idt', ''))
        ET.SubElement(voucher, "DATE").text = invoice_date
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Purchase"
        ET.SubElement(voucher, "VOUCHERNUMBER").text = str(voucher_number)
        ET.SubElement(voucher, "REFERENCE").text = invoice.get('inum', '')
        
        # Vendor ledger entry (Credit)
        vendor_name = f"Vendor - {vendor_gstin}"
        vendor_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(vendor_entry, "LEDGERNAME").text = vendor_name
        ET.SubElement(vendor_entry, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(vendor_entry, "AMOUNT").text = f"-{invoice.get('val', 0):.2f}"
        
        # Process items
        for item in invoice.get('itms', []):
            item_det = item.get('itm_det', {})
            
            # Purchase entry (Debit)
            purchase_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(purchase_entry, "LEDGERNAME").text = f"Purchase - HSN {item_det.get('hsn_sc', 'Unknown')}"
            ET.SubElement(purchase_entry, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(purchase_entry, "AMOUNT").text = f"{item_det.get('txval', 0):.2f}"
            
            # Tax entries
            if item_det.get('iamt', 0) > 0:
                # IGST
                igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(igst_entry, "LEDGERNAME").text = f"Input IGST {item_det.get('rt', 0)}%"
                ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "No"
                ET.SubElement(igst_entry, "AMOUNT").text = f"{item_det.get('iamt', 0):.2f}"
            else:
                # CGST/SGST
                if item_det.get('camt', 0) > 0:
                    cgst_rate = item_det.get('rt', 0) / 2
                    cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(cgst_entry, "LEDGERNAME").text = f"Input CGST {cgst_rate}%"
                    ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "No"
                    ET.SubElement(cgst_entry, "AMOUNT").text = f"{item_det.get('camt', 0):.2f}"
                
                if item_det.get('samt', 0) > 0:
                    sgst_rate = item_det.get('rt', 0) / 2
                    sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(sgst_entry, "LEDGERNAME").text = f"Input SGST {sgst_rate}%"
                    ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "No"
                    ET.SubElement(sgst_entry, "AMOUNT").text = f"{item_det.get('samt', 0):.2f}"
    
    def _add_sales_voucher_from_gst(self, parent: ET.Element, customer_gstin: str, invoice: Dict[str, Any], voucher_number: int):
        """Add sales voucher from GST data."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        voucher = ET.SubElement(msg, "VOUCHER")
        voucher.set("VCHTYPE", "Sales")
        voucher.set("ACTION", "Create")
        
        # Voucher details
        invoice_date = self._format_gst_date(invoice.get('idt', ''))
        ET.SubElement(voucher, "DATE").text = invoice_date
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Sales"
        ET.SubElement(voucher, "VOUCHERNUMBER").text = str(voucher_number)
        ET.SubElement(voucher, "REFERENCE").text = invoice.get('inum', '')
        
        # Customer ledger entry (Debit)
        customer_name = f"Customer - {customer_gstin}"
        customer_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(customer_entry, "LEDGERNAME").text = customer_name
        ET.SubElement(customer_entry, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(customer_entry, "AMOUNT").text = f"{invoice.get('val', 0):.2f}"
        
        # Process items
        for item in invoice.get('itms', []):
            item_det = item.get('itm_det', {})
            
            # Sales entry (Credit)
            sales_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(sales_entry, "LEDGERNAME").text = f"Sales - HSN {item_det.get('hsn_sc', 'Unknown')}"
            ET.SubElement(sales_entry, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(sales_entry, "AMOUNT").text = f"-{item_det.get('txval', 0):.2f}"
            
            # Tax entries
            if item_det.get('iamt', 0) > 0:
                # IGST
                igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(igst_entry, "LEDGERNAME").text = f"Output IGST {item_det.get('rt', 0)}%"
                ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                ET.SubElement(igst_entry, "AMOUNT").text = f"-{item_det.get('iamt', 0):.2f}"
            else:
                # CGST/SGST
                if item_det.get('camt', 0) > 0:
                    cgst_rate = item_det.get('rt', 0) / 2
                    cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(cgst_entry, "LEDGERNAME").text = f"Output CGST {cgst_rate}%"
                    ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                    ET.SubElement(cgst_entry, "AMOUNT").text = f"-{item_det.get('camt', 0):.2f}"
                
                if item_det.get('samt', 0) > 0:
                    sgst_rate = item_det.get('rt', 0) / 2
                    sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(sgst_entry, "LEDGERNAME").text = f"Output SGST {sgst_rate}%"
                    ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                    ET.SubElement(sgst_entry, "AMOUNT").text = f"-{item_det.get('samt', 0):.2f}"
    
    def _add_b2cl_sales_voucher(self, parent: ET.Element, invoice: Dict[str, Any], voucher_number: int):
        """Add B2CL sales voucher."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        voucher = ET.SubElement(msg, "VOUCHER")
        voucher.set("VCHTYPE", "Sales")
        voucher.set("ACTION", "Create")
        
        # Voucher details
        invoice_date = self._format_gst_date(invoice.get('idt', ''))
        ET.SubElement(voucher, "DATE").text = invoice_date
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Sales"
        ET.SubElement(voucher, "VOUCHERNUMBER").text = str(voucher_number)
        ET.SubElement(voucher, "REFERENCE").text = invoice.get('inum', '')
        
        # Customer ledger entry (Debit) - use generic B2CL customer
        customer_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(customer_entry, "LEDGERNAME").text = "B2CL Customers"
        ET.SubElement(customer_entry, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(customer_entry, "AMOUNT").text = f"{invoice.get('val', 0):.2f}"
        
        # Process items
        for item in invoice.get('itms', []):
            item_det = item.get('itm_det', {})
            
            # Sales entry (Credit)
            sales_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(sales_entry, "LEDGERNAME").text = f"Sales - HSN {item_det.get('hsn_sc', 'Unknown')}"
            ET.SubElement(sales_entry, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(sales_entry, "AMOUNT").text = f"-{item_det.get('txval', 0):.2f}"
            
            # Tax entries (similar to B2B)
            if item_det.get('iamt', 0) > 0:
                igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(igst_entry, "LEDGERNAME").text = f"Output IGST {item_det.get('rt', 0)}%"
                ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                ET.SubElement(igst_entry, "AMOUNT").text = f"-{item_det.get('iamt', 0):.2f}"
            else:
                if item_det.get('camt', 0) > 0:
                    cgst_rate = item_det.get('rt', 0) / 2
                    cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(cgst_entry, "LEDGERNAME").text = f"Output CGST {cgst_rate}%"
                    ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                    ET.SubElement(cgst_entry, "AMOUNT").text = f"-{item_det.get('camt', 0):.2f}"
                
                if item_det.get('samt', 0) > 0:
                    sgst_rate = item_det.get('rt', 0) / 2
                    sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(sgst_entry, "LEDGERNAME").text = f"Output SGST {sgst_rate}%"
                    ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                    ET.SubElement(sgst_entry, "AMOUNT").text = f"-{item_det.get('samt', 0):.2f}"
    
    def _format_gst_date(self, date_str: str) -> str:
        """Format GST date to Tally format."""
        if not date_str:
            return datetime.now().strftime("%Y%m%d")
        
        try:
            # GST dates are usually in DD-MM-YYYY format
            if '-' in date_str:
                dt = datetime.strptime(date_str, "%d-%m-%Y")
                return dt.strftime("%Y%m%d")
            else:
                return datetime.now().strftime("%Y%m%d")
        except Exception as e:
            logger.error(f"Error formatting GST date {date_str}: {e}")
            return datetime.now().strftime("%Y%m%d")
    
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