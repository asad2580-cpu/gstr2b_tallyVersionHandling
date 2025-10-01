import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
import logging
from gstr2b_dedicated_processor import GSTR2BVendor

logger = logging.getLogger(__name__)

class GSTR2BMastersXMLGenerator:
    """Generate Masters XML for GSTR2B vendor ledgers to import into Tally."""
    
    def __init__(self, company_name: str, company_state: str):
        """
        Initialize GSTR2B Masters XML generator.
        
        Args:
            company_name: Name of the company in Tally
            company_state: Company's state for GST ledger creation
        """
        self.company_name = company_name
        self.company_state = company_state
    
    def generate_masters_xml(self, vendors: List[GSTR2BVendor], metadata: Dict[str, Any]) -> str:
        """
        Generate Masters XML containing all vendor ledgers and GST tax ledgers.
        
        Args:
            vendors: List of GSTR2BVendor objects
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
            ET.SubElement(header, "ID").text = "All Masters"
            
            # Body
            body = ET.SubElement(envelope, "BODY")
            import_data = ET.SubElement(body, "IMPORTDATA")
            
            # Request description
            request_desc = ET.SubElement(import_data, "REQUESTDESC")
            ET.SubElement(request_desc, "REPORTNAME").text = "All Masters"
            static_vars = ET.SubElement(request_desc, "STATICVARIABLES")
            ET.SubElement(static_vars, "SVCURRENTCOMPANY").text = self.company_name
            
            # Request data
            request_data = ET.SubElement(import_data, "REQUESTDATA")
            
            # Create groups first
            self._create_ledger_groups(request_data)
            
            # Create GST tax ledgers
            self._create_gst_tax_ledgers(request_data, vendors)
            
            # Create vendor ledgers
            self._create_vendor_ledgers(request_data, vendors)
            
            # Create purchase ledgers
            self._create_purchase_ledgers(request_data)
            
            return self._prettify_xml(envelope)
            
        except Exception as e:
            logger.error(f"Error generating GSTR2B Masters XML: {e}")
            return ""
    
    def _create_ledger_groups(self, parent: ET.Element):
        """Create required ledger groups."""
        # Sundry Creditors group (if needed)
        self._create_group(parent, "GSTR2B Suppliers", "Sundry Creditors")
        
        # GST tax groups
        self._create_group(parent, "GST Input Tax", "Duties & Taxes")
        
        # Purchase groups
        self._create_group(parent, "GSTR2B Purchases", "Purchase Accounts")
    
    def _create_group(self, parent: ET.Element, group_name: str, under_group: str):
        """Create a ledger group."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        group = ET.SubElement(msg, "GROUP")
        group.set("NAME", group_name)
        ET.SubElement(group, "NAME").text = group_name
        group.set("ACTION", "Create")
        ET.SubElement(group, "PARENT").text = under_group
        ET.SubElement(group, "ISSUBLEDGER").text = "No"
    
    def _create_gst_tax_ledgers(self, parent: ET.Element, vendors: List[GSTR2BVendor]):
        """Create GST input tax ledgers based on data."""
        tax_rates = set()
        
        # Collect all tax rates from vendor data
        for vendor in vendors:
            for invoice in vendor.invoices:
                txval = float(invoice.get('txval', 0))
                cgst = float(invoice.get('cgst', 0))
                sgst = float(invoice.get('sgst', 0))
                igst = float(invoice.get('igst', 0))
                
                # Calculate rates
                if txval > 0:
                    if cgst > 0:
                        cgst_rate = round((cgst / txval) * 100)
                        tax_rates.add(cgst_rate)
                    if sgst > 0:
                        sgst_rate = round((sgst / txval) * 100)
                        tax_rates.add(sgst_rate)
                    if igst > 0:
                        igst_rate = round((igst / txval) * 100)
                        tax_rates.add(igst_rate)
        
        # Create tax ledgers for each rate found
        for rate in sorted(tax_rates):
            if rate > 0:
                # Input CGST
                self._create_tax_ledger(parent, f"Input CGST {rate}%", "GST Input Tax")
                # Input SGST
                self._create_tax_ledger(parent, f"Input SGST {rate}%", "GST Input Tax")
                # Input IGST (use the actual IGST rate)
                self._create_tax_ledger(parent, f"Input IGST {rate}%", "GST Input Tax")
        
        # Create common tax ledgers that might be needed
        common_rates = [2.5, 6, 9, 14, 18, 28]
        for rate in common_rates:
            self._create_tax_ledger(parent, f"Input CGST {rate}%", "GST Input Tax")
            self._create_tax_ledger(parent, f"Input SGST {rate}%", "GST Input Tax")
            self._create_tax_ledger(parent, f"Input IGST {rate}%", "GST Input Tax")
        
        # Create CESS ledger (if applicable)
        self._create_tax_ledger(parent, "Input CESS", "GST Input Tax")
    
    def _create_tax_ledger(self, parent: ET.Element, ledger_name: str, group_name: str):
        """Create a GST tax ledger."""
        msg = ET.SubElement(parent, "TALLYMESSAGE")
        msg.set("xmlns:UDF", "TallyUDF")
        ledger = ET.SubElement(msg, "LEDGER")
        ledger.set("NAME", ledger_name)
        ET.SubElement(ledger, "NAME").text = ledger_name
        ledger.set("ACTION", "Create")
        ET.SubElement(ledger, "PARENT").text = group_name
        ET.SubElement(ledger, "TAXCLASSIFICATIONNAME").text = "GST"
        ET.SubElement(ledger, "TAXTYPE").text = "GST"
        ET.SubElement(ledger, "GSTTYPE").text = "Input"
        ET.SubElement(ledger, "APPROPRIATEFOR").text = "Both"
    
    def _create_vendor_ledgers(self, parent: ET.Element, vendors: List[GSTR2BVendor]):
        """Create vendor ledgers for all suppliers."""
        for vendor in vendors:
            vendor_name = self._clean_ledger_name(vendor.trdnm or f"Vendor-{vendor.ctin}")
            
            msg = ET.SubElement(parent, "TALLYMESSAGE")
            msg.set("xmlns:UDF", "TallyUDF")
            ledger = ET.SubElement(msg, "LEDGER")
            ledger.set("NAME", vendor_name)
            ET.SubElement(ledger, "NAME").text = vendor_name
            ledger.set("ACTION", "Create")
            
            # Basic ledger details
            ET.SubElement(ledger, "PARENT").text = "GSTR2B Suppliers"
            ET.SubElement(ledger, "ISBILLWISEON").text = "Yes"
            ET.SubElement(ledger, "ISCOSTCENTRESON").text = "No"
            
            # GST details
            if vendor.ctin:
                ET.SubElement(ledger, "PARTYGSTIN").text = vendor.ctin
                ET.SubElement(ledger, "GSTREGISTRATIONTYPE").text = "Regular"
                
                # State from GSTIN (first 2 digits)
                state_code = vendor.ctin[:2] if len(vendor.ctin) >= 2 else "07"
                ET.SubElement(ledger, "STATECODE").text = state_code
            
            # Address (basic)
            address = ET.SubElement(ledger, "ADDRESS.LIST")
            ET.SubElement(address, "ADDRESS").text = f"Supplier: {vendor.trdnm}"
            
            # Opening balance (usually zero for new ledgers)
            ET.SubElement(ledger, "OPENINGBALANCE").text = "0.00"
    
    def _create_purchase_ledgers(self, parent: ET.Element):
        """Create purchase ledgers for different categories."""
        purchase_categories = [
            "Purchase - Trading Goods",
            "Purchase - Raw Materials", 
            "Purchase - Consumables",
            "Purchase - Capital Goods",
            "Purchase - Services"
        ]
        
        for category in purchase_categories:
            msg = ET.SubElement(parent, "TALLYMESSAGE")
            msg.set("xmlns:UDF", "TallyUDF")
            ledger = ET.SubElement(msg, "LEDGER")
            ledger.set("NAME", category)
            ET.SubElement(ledger, "NAME").text = category
            ledger.set("ACTION", "Create")
            ET.SubElement(ledger, "PARENT").text = "GSTR2B Purchases"
            ET.SubElement(ledger, "ISCOSTCENTRESON").text = "No"
    
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
    
    def validate_masters_xml(self, vendors: List[GSTR2BVendor]) -> Dict[str, Any]:
        """Validate masters data before XML generation."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if not vendors:
            validation_result['valid'] = False
            validation_result['errors'].append("No vendors found for Masters XML generation")
            return validation_result
        
        # Check for duplicate vendor names
        vendor_names = [self._clean_ledger_name(v.trdnm or f"Vendor-{v.ctin}") for v in vendors]
        duplicates = set([name for name in vendor_names if vendor_names.count(name) > 1])
        
        if duplicates:
            validation_result['warnings'].append(f"Duplicate vendor names found: {list(duplicates)}")
        
        # Check for vendors without GSTIN
        vendors_without_gstin = [v for v in vendors if not v.ctin]
        if vendors_without_gstin:
            validation_result['warnings'].append(f"{len(vendors_without_gstin)} vendors without GSTIN found")
        
        validation_result['summary'] = {
            'total_vendors': len(vendors),
            'vendors_with_gstin': len([v for v in vendors if v.ctin]),
            'total_invoices': sum(v.total_invoices for v in vendors)
        }
        
        return validation_result