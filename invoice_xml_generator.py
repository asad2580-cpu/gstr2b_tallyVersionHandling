import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InvoiceXMLGenerator:
    def __init__(self, company_name: str, company_state: str):
        """
        Initialize Invoice XML generator.
        
        Args:
            company_name: Name of the company in Tally
            company_state: Company state for GST calculations
        """
        self.company_name = company_name
        self.company_state = company_state
        
    def generate_purchase_xml(self, invoice_data: Dict[str, Any]) -> str:
        """Generate Tally XML for purchase invoice."""
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
        
        # Create ledgers if they don't exist
        self._add_purchase_ledgers(request_data, invoice_data)
        
        # Add purchase voucher
        self._add_purchase_voucher(request_data, invoice_data)
        
        return self._prettify_xml(envelope)
    
    def generate_sales_xml(self, invoice_data: Dict[str, Any]) -> str:
        """Generate Tally XML for sales invoice."""
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
        
        # Create ledgers if they don't exist
        self._add_sales_ledgers(request_data, invoice_data)
        
        # Add sales voucher
        self._add_sales_voucher(request_data, invoice_data)
        
        return self._prettify_xml(envelope)
    
    def _add_purchase_ledgers(self, parent: ET.Element, invoice_data: Dict[str, Any]):
        """Add required ledgers for purchase invoice."""
        vendor_name = invoice_data.get('vendor_name', 'Unknown Vendor')
        
        # Vendor ledger
        vendor_msg = ET.SubElement(parent, "TALLYMESSAGE")
        vendor_msg.set("xmlns:UDF", "TallyUDF")
        vendor_ledger = ET.SubElement(vendor_msg, "LEDGER")
        vendor_ledger.set("NAME", vendor_name)
        vendor_ledger.set("ACTION", "Create")
        ET.SubElement(vendor_ledger, "PARENT").text = "Sundry Creditors"
        ET.SubElement(vendor_ledger, "ISBILLWISEON").text = "Yes"
        
        # Tax ledgers based on interstate/intrastate
        is_interstate = self._is_interstate_transaction(invoice_data.get('vendor_state'))
        
        if is_interstate:
            # IGST ledgers
            for item in invoice_data.get('items', []):
                if item.get('igst_rate'):
                    igst_rate = item['igst_rate']
                    igst_ledger_name = f"Input IGST {igst_rate}%"
                    self._create_tax_ledger(parent, igst_ledger_name, "Duties & Taxes")
        else:
            # CGST/SGST ledgers
            for item in invoice_data.get('items', []):
                if item.get('cgst_rate'):
                    cgst_rate = item['cgst_rate']
                    sgst_rate = item.get('sgst_rate', cgst_rate)
                    cgst_ledger_name = f"Input CGST {cgst_rate}%"
                    sgst_ledger_name = f"Input SGST {sgst_rate}%"
                    self._create_tax_ledger(parent, cgst_ledger_name, "Duties & Taxes")
                    self._create_tax_ledger(parent, sgst_ledger_name, "Duties & Taxes")
        
        # Purchase ledgers for items
        for item in invoice_data.get('items', []):
            description = item.get('description', 'Purchase Item')
            purchase_ledger_name = f"Purchase - {description[:30]}"
            self._create_expense_ledger(parent, purchase_ledger_name)
    
    def _add_sales_ledgers(self, parent: ET.Element, invoice_data: Dict[str, Any]):
        """Add required ledgers for sales invoice."""
        buyer_name = invoice_data.get('buyer_name', 'Unknown Customer')
        
        # Customer ledger
        customer_msg = ET.SubElement(parent, "TALLYMESSAGE")
        customer_msg.set("xmlns:UDF", "TallyUDF")
        customer_ledger = ET.SubElement(customer_msg, "LEDGER")
        customer_ledger.set("NAME", buyer_name)
        customer_ledger.set("ACTION", "Create")
        ET.SubElement(customer_ledger, "PARENT").text = "Sundry Debtors"
        ET.SubElement(customer_ledger, "ISBILLWISEON").text = "Yes"
        
        # Tax ledgers based on interstate/intrastate
        is_interstate = self._is_interstate_transaction(invoice_data.get('buyer_state'))
        
        if is_interstate:
            # IGST ledgers
            for item in invoice_data.get('items', []):
                if item.get('igst_rate'):
                    igst_rate = item['igst_rate']
                    igst_ledger_name = f"Output IGST {igst_rate}%"
                    self._create_tax_ledger(parent, igst_ledger_name, "Duties & Taxes")
        else:
            # CGST/SGST ledgers
            for item in invoice_data.get('items', []):
                if item.get('cgst_rate'):
                    cgst_rate = item['cgst_rate']
                    sgst_rate = item.get('sgst_rate', cgst_rate)
                    cgst_ledger_name = f"Output CGST {cgst_rate}%"
                    sgst_ledger_name = f"Output SGST {sgst_rate}%"
                    self._create_tax_ledger(parent, cgst_ledger_name, "Duties & Taxes")
                    self._create_tax_ledger(parent, sgst_ledger_name, "Duties & Taxes")
        
        # Sales ledgers for items
        for item in invoice_data.get('items', []):
            description = item.get('description', 'Sales Item')
            sales_ledger_name = f"Sales - {description[:30]}"
            self._create_income_ledger(parent, sales_ledger_name)
    
    def _create_tax_ledger(self, parent: ET.Element, ledger_name: str, parent_group: str):
        """Create a tax ledger."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        ledger = ET.SubElement(msg, "LEDGER")
        ledger.set("NAME", ledger_name)
        ledger.set("ACTION", "Create")
        ET.SubElement(ledger, "PARENT").text = parent_group
        ET.SubElement(ledger, "TAXTYPE").text = "GST"
    
    def _create_expense_ledger(self, parent: ET.Element, ledger_name: str):
        """Create an expense ledger for purchases."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        ledger = ET.SubElement(msg, "LEDGER")
        ledger.set("NAME", ledger_name)
        ledger.set("ACTION", "Create")
        ET.SubElement(ledger, "PARENT").text = "Purchase Accounts"
    
    def _create_income_ledger(self, parent: ET.Element, ledger_name: str):
        """Create an income ledger for sales."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        ledger = ET.SubElement(msg, "LEDGER")
        ledger.set("NAME", ledger_name)
        ledger.set("ACTION", "Create")
        ET.SubElement(ledger, "PARENT").text = "Sales Accounts"
    
    def _add_purchase_voucher(self, parent: ET.Element, invoice_data: Dict[str, Any]):
        """Add purchase voucher to XML."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        voucher = ET.SubElement(msg, "VOUCHER")
        voucher.set("VCHTYPE", "Purchase")
        voucher.set("ACTION", "Create")
        
        # Voucher details
        invoice_date = self._format_date(invoice_data.get('invoice_date', ''))
        ET.SubElement(voucher, "DATE").text = invoice_date
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Purchase"
        ET.SubElement(voucher, "VOUCHERNUMBER").text = invoice_data.get('invoice_number', '')
        ET.SubElement(voucher, "REFERENCE").text = invoice_data.get('invoice_number', '')
        
        # Vendor ledger entry (Credit)
        vendor_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(vendor_entry, "LEDGERNAME").text = invoice_data.get('vendor_name', 'Unknown Vendor')
        ET.SubElement(vendor_entry, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(vendor_entry, "AMOUNT").text = f"-{invoice_data.get('total_invoice_value', 0):.2f}"
        
        # Item and tax entries
        is_interstate = self._is_interstate_transaction(invoice_data.get('vendor_state'))
        
        for item in invoice_data.get('items', []):
            # Purchase item entry (Debit)
            item_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            item_ledger_name = f"Purchase - {item.get('description', 'Item')[:30]}"
            ET.SubElement(item_entry, "LEDGERNAME").text = item_ledger_name
            ET.SubElement(item_entry, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(item_entry, "AMOUNT").text = f"{item.get('taxable_value', 0):.2f}"
            
            # Tax entries (Debit)
            if is_interstate and item.get('igst_amount', 0) > 0:
                igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(igst_entry, "LEDGERNAME").text = f"Input IGST {item.get('igst_rate', 0)}%"
                ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "No"
                ET.SubElement(igst_entry, "AMOUNT").text = f"{item.get('igst_amount', 0):.2f}"
            else:
                if item.get('cgst_amount', 0) > 0:
                    cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(cgst_entry, "LEDGERNAME").text = f"Input CGST {item.get('cgst_rate', 0)}%"
                    ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "No"
                    ET.SubElement(cgst_entry, "AMOUNT").text = f"{item.get('cgst_amount', 0):.2f}"
                
                if item.get('sgst_amount', 0) > 0:
                    sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(sgst_entry, "LEDGERNAME").text = f"Input SGST {item.get('sgst_rate', 0)}%"
                    ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "No"
                    ET.SubElement(sgst_entry, "AMOUNT").text = f"{item.get('sgst_amount', 0):.2f}"
    
    def _add_sales_voucher(self, parent: ET.Element, invoice_data: Dict[str, Any]):
        """Add sales voucher to XML."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        voucher = ET.SubElement(msg, "VOUCHER")
        voucher.set("VCHTYPE", "Sales")
        voucher.set("ACTION", "Create")
        
        # Voucher details
        invoice_date = self._format_date(invoice_data.get('invoice_date', ''))
        ET.SubElement(voucher, "DATE").text = invoice_date
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = "Sales"
        ET.SubElement(voucher, "VOUCHERNUMBER").text = invoice_data.get('invoice_number', '')
        ET.SubElement(voucher, "REFERENCE").text = invoice_data.get('invoice_number', '')
        
        # Customer ledger entry (Debit)
        customer_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(customer_entry, "LEDGERNAME").text = invoice_data.get('buyer_name', 'Unknown Customer')
        ET.SubElement(customer_entry, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(customer_entry, "AMOUNT").text = f"{invoice_data.get('total_invoice_value', 0):.2f}"
        
        # Item and tax entries
        is_interstate = self._is_interstate_transaction(invoice_data.get('buyer_state'))
        
        for item in invoice_data.get('items', []):
            # Sales item entry (Credit)
            item_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
            item_ledger_name = f"Sales - {item.get('description', 'Item')[:30]}"
            ET.SubElement(item_entry, "LEDGERNAME").text = item_ledger_name
            ET.SubElement(item_entry, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(item_entry, "AMOUNT").text = f"-{item.get('taxable_value', 0):.2f}"
            
            # Tax entries (Credit)
            if is_interstate and item.get('igst_amount', 0) > 0:
                igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                ET.SubElement(igst_entry, "LEDGERNAME").text = f"Output IGST {item.get('igst_rate', 0)}%"
                ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                ET.SubElement(igst_entry, "AMOUNT").text = f"-{item.get('igst_amount', 0):.2f}"
            else:
                if item.get('cgst_amount', 0) > 0:
                    cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(cgst_entry, "LEDGERNAME").text = f"Output CGST {item.get('cgst_rate', 0)}%"
                    ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                    ET.SubElement(cgst_entry, "AMOUNT").text = f"-{item.get('cgst_amount', 0):.2f}"
                
                if item.get('sgst_amount', 0) > 0:
                    sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
                    ET.SubElement(sgst_entry, "LEDGERNAME").text = f"Output SGST {item.get('sgst_rate', 0)}%"
                    ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
                    ET.SubElement(sgst_entry, "AMOUNT").text = f"-{item.get('sgst_amount', 0):.2f}"
    
    def _is_interstate_transaction(self, other_state: str | None) -> bool:
        """Check if transaction is interstate."""
        if not other_state:
            return False
        return other_state.strip().lower() != self.company_state.strip().lower()
    
    def _format_date(self, date_str: str) -> str:
        """Format date for Tally (YYYYMMDD)."""
        if not date_str:
            return datetime.now().strftime("%Y%m%d")
        
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y%m%d")
                except ValueError:
                    continue
            
            logger.warning(f"Could not parse date: {date_str}, using current date")
            return datetime.now().strftime("%Y%m%d")
            
        except Exception as e:
            logger.error(f"Error formatting date {date_str}: {e}")
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