import streamlit as st
import json
import os
from datetime import datetime
from PIL import Image
import io
from pdf2image import convert_from_bytes
from transaction_extractor import TransactionExtractor
from tally_xml_generator import TallyXMLGenerator
from gst_processor import GSTProcessor
from invoice_extractor import InvoiceExtractor
from invoice_xml_generator import InvoiceXMLGenerator
from gst_portal_json_generator import GSTPortalJSONGenerator
from gst_tally_xml_generator import GSTTallyXMLGenerator
from gstr2b_dedicated_processor import GSTR2BDedicatedProcessor
from gstr2b_masters_xml import GSTR2BMastersXMLGenerator
from gstr2b_transactions_xml import GSTR2BTransactionsXMLGenerator

# Set page configuration
st.set_page_config(
    page_title="Tally ERP Automation Suite",
    page_icon="🏛️",
    layout="wide"
)

def convert_file_to_png_bytes(uploaded_file) -> bytes:
    """
    Convert uploaded file (PNG, JPG, JPEG, PDF) to PNG bytes.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        PNG image bytes
    """
    file_bytes = uploaded_file.read()
    file_extension = uploaded_file.name.lower().split('.')[-1]
    
    try:
        if file_extension == 'pdf':
            # Convert PDF to images (take first page)
            images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=200)
            if images:
                # Convert PIL Image to PNG bytes
                img_bytes = io.BytesIO()
                images[0].save(img_bytes, format='PNG')
                return img_bytes.getvalue()
            else:
                raise ValueError("No images found in PDF")
        
        elif file_extension in ['jpg', 'jpeg']:
            # Convert JPG/JPEG to PNG
            image = Image.open(io.BytesIO(file_bytes))
            # Convert to RGB if needed (JPEG can be in different modes)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
        
        elif file_extension == 'png':
            # Already PNG, return as-is
            return file_bytes
        
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
            
    except Exception as e:
        raise Exception(f"Error converting {file_extension.upper()} file: {str(e)}")

# Initialize the transaction extractor
@st.cache_resource
def get_extractor():
    return TransactionExtractor()

def main():
    st.title("🏛️ Tally ERP Automation Suite")
    st.markdown("Comprehensive automation solution for importing bank statements, invoices, and GST returns into Tally")
    
    # Check if API key is available
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY environment variable not found. Please set your Gemini API key.")
        st.stop()
    
    # Global Configuration Section
    st.subheader("⚙️ Company Configuration")
    col_config1, col_config2 = st.columns(2)
    
    with col_config1:
        company_name = st.text_input(
            "Company Name (as in Tally)",
            placeholder="Enter your company name exactly as it appears in Tally",
            help="This should match your company name in Tally exactly"
        )
    
    with col_config2:
        company_state = st.selectbox(
            "Company State",
            options=[
                "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
                "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
                "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
                "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Puducherry"
            ],
            index=None,
            placeholder="Select your company's state",
            help="Required for accurate GST bifurcation (CGST+SGST vs IGST)"
        )
    
    # Show configuration status
    config_status = []
    if company_name:
        config_status.append(f"Company: {company_name}")
    if company_state:
        config_status.append(f"State: {company_state}")
    
    if config_status:
        st.success(f"✅ Configuration: {' | '.join(config_status)}")
    else:
        st.info("💡 Please configure company details above to proceed")
    
    st.divider()
    
    # Create tabs for different document types
    tab_bank, tab_invoice, tab_gst = st.tabs(["🏦 Bank Statements", "📄 Invoices", "📊 GST Returns"])
    
    with tab_bank:
        process_bank_statements(company_name)
    
    with tab_invoice:
        process_invoices(company_name, company_state)
    
    with tab_gst:
        process_gst_returns(company_name, company_state)

def process_bank_statements(company_name: str):
    """Handle bank statement processing."""
    st.subheader("🏦 Bank Statement Processing")
    st.markdown("Upload bank statement images/PDFs to extract transaction data and generate Tally XML")
    
    # Bank Account Configuration
    st.subheader("💰 Bank Account Configuration")
    bank_ledger_name = st.text_input(
        "Bank Ledger Name", 
        placeholder="e.g., HDFC Bank, SBI Current Account",
        help="Name of the bank account ledger in your Tally (required for XML generation)",
        key="bank_ledger_input"
    )
    
    if bank_ledger_name:
        st.success(f"✅ Bank Account: {bank_ledger_name}")
    else:
        st.info("💡 Please enter your bank ledger name to proceed with Tally XML generation")
    
    st.divider()
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a bank statement file",
        type=['png', 'jpg', 'jpeg', 'pdf'],
        accept_multiple_files=False,
        help="Upload a clear image or PDF of your bank statement (PNG, JPG, JPEG, PDF formats supported)",
        key="bank_statement_uploader"
    )
    
    if uploaded_file is not None:
        # Convert file to PNG format for processing
        try:
            png_bytes = convert_file_to_png_bytes(uploaded_file)
            original_format = uploaded_file.name.lower().split('.')[-1].upper()
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return
        
        # Display uploaded file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"📄 Uploaded {original_format} File")
            try:
                # Display the converted PNG image
                display_image = Image.open(io.BytesIO(png_bytes))
                st.image(display_image, caption=f"Bank Statement ({original_format})", use_column_width=True)
                
                # File info
                st.info(f"**File Details:**\n- Original Format: {original_format}\n- Size: {display_image.size[0]} x {display_image.size[1]} pixels\n- Processed Format: PNG\n- Mode: {display_image.mode}")
                
            except Exception as e:
                st.error(f"Error displaying image: {str(e)}")
                return
        
        with col2:
            st.subheader("🔄 Transaction Extraction")
            
            # Check if transactions are already extracted
            if 'extracted_transactions' in st.session_state and st.session_state.get('extraction_completed', False):
                st.success(f"✅ {len(st.session_state['extracted_transactions'])} transactions already extracted!")
                if st.button("🔄 Re-extract Transactions", type="secondary"):
                    # Clear existing data and re-extract
                    if 'extracted_transactions' in st.session_state:
                        del st.session_state['extracted_transactions']
                    if 'extraction_completed' in st.session_state:
                        del st.session_state['extraction_completed']
                    if 'tally_xml' in st.session_state:
                        del st.session_state['tally_xml']
                    st.rerun()
            else:
                if st.button("Extract Transactions", type="primary"):
                    try:
                        # Show progress
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        status_text.text("🔍 Analyzing image...")
                        progress_bar.progress(25)
                        
                        # Get extractor
                        extractor = get_extractor()
                        
                        status_text.text("🤖 Processing with AI...")
                        progress_bar.progress(50)
                        
                        status_text.text("📊 Extracting transaction data...")
                        progress_bar.progress(75)
                        
                        # Extract transactions using already converted PNG bytes
                        transactions = extractor.extract_transactions(png_bytes)
                        
                        status_text.text("✅ Complete!")
                        progress_bar.progress(100)
                        
                        # Store transactions in session state for persistence
                        st.session_state['extracted_transactions'] = transactions
                        st.session_state['extraction_completed'] = True
                        
                        # Clear progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        
                        if transactions:
                            st.success(f"🎉 Successfully extracted {len(transactions)} transactions!")
                        else:
                            st.warning("⚠️ No transactions found in the image. Please ensure the image is clear and contains transaction data.")
                            
                    except Exception as e:
                        st.error(f"❌ Error processing image: {str(e)}")
                        st.error("Please try again with a different image or check if the image is clear and readable.")
        
        # Display extracted transactions if available
        if 'extracted_transactions' in st.session_state and st.session_state.get('extraction_completed', False):
            transactions = st.session_state['extracted_transactions']
            
            if transactions:
                st.divider()
                st.subheader("📋 Extracted Transactions")
                
                # Create tabs for different views
                tab1, tab2, tab3, tab4 = st.tabs(["📊 Table View", "📄 JSON View", "🔄 Tally XML", "💾 Download"])
                
                with tab1:
                    # Display as dataframe
                    import pandas as pd
                    df = pd.DataFrame(transactions)
                    st.dataframe(df, use_container_width=True)
                            
                    # Summary statistics
                    if len(transactions) > 0:
                        st.subheader("📈 Summary")
                        col_a, col_b, col_c = st.columns(3)
                        
                        total_debits = sum(float(t.get('debit_amount', 0) or 0) for t in transactions)
                        total_credits = sum(float(t.get('credit_amount', 0) or 0) for t in transactions)
                        
                        with col_a:
                            st.metric("Total Transactions", len(transactions))
                        with col_b:
                            st.metric("Total Debits", f"₹{total_debits:,.2f}")
                        with col_c:
                            st.metric("Total Credits", f"₹{total_credits:,.2f}")
                        
                        with tab2:
                            # Display as JSON
                            json_str = json.dumps(transactions, indent=2)
                            st.code(json_str, language="json")
                        
                        with tab3:
                            # Tally XML Generation
                            if company_name and bank_ledger_name:
                                st.subheader("🔄 Generate Tally XML")
                                
                                try:
                                    # Initialize XML generator
                                    xml_generator = TallyXMLGenerator(company_name, bank_ledger_name)
                                    
                                    # Validate data before generation
                                    validation_result = xml_generator.validate_xml_structure(transactions)
                                    
                                    # Show validation results
                                    if validation_result['valid']:
                                        st.success(f"✅ Ready to generate XML for {validation_result['transaction_count']} transactions")
                                        
                                        if validation_result['warnings']:
                                            with st.expander("⚠️ Validation Warnings"):
                                                for warning in validation_result['warnings']:
                                                    st.warning(warning)
                                        
                                        # Generate XML button
                                        if st.button("🔄 Generate Tally XML", type="primary"):
                                            with st.spinner("Generating Tally XML..."):
                                                xml_content = xml_generator.generate_xml(transactions)
                                                
                                                st.success("✅ Tally XML generated successfully!")
                                                
                                                # Display XML preview (first 2000 chars)
                                                st.subheader("📄 XML Preview")
                                                preview_xml = xml_content[:2000]
                                                if len(xml_content) > 2000:
                                                    preview_xml += "\n... (truncated, full XML available in download)"
                                                
                                                st.code(preview_xml, language="xml")
                                                
                                                # Store XML in session state for download
                                                st.session_state['tally_xml'] = xml_content
                                                
                                                # Quick info about the XML
                                                st.info(f"""
                                                **XML Details:**
                                                - Company: {company_name}
                                                - Bank Ledger: {bank_ledger_name}
                                                - Suspense Ledger: Suspense (auto-created if needed)
                                                - Transactions: {len(transactions)}
                                                - XML Size: {len(xml_content)} characters
                                                """)
                                    else:
                                        st.error("❌ Validation failed. Please fix the following errors:")
                                        for error in validation_result['errors']:
                                            st.error(f"• {error}")
                                        
                                        if validation_result['warnings']:
                                            st.warning("Additional warnings:")
                                            for warning in validation_result['warnings']:
                                                st.warning(f"• {warning}")
                                                
                                except Exception as e:
                                    st.error(f"❌ Error generating XML: {str(e)}")
                            else:
                                st.warning("⚠️ Please configure company name and bank ledger name in the settings above to generate Tally XML")
                        
                        with tab4:
                            # Download options
                            st.subheader("💾 Download Options")
                            
                            col_dl1, col_dl2, col_dl3 = st.columns(3)
                            
                            with col_dl1:
                                # JSON download
                                json_str = json.dumps(transactions, indent=2)
                                st.download_button(
                                    label="📄 Download JSON",
                                    data=json_str,
                                    file_name="bank_transactions.json",
                                    mime="application/json"
                                )
                            
                            with col_dl2:
                                # CSV download
                                if transactions:
                                    import pandas as pd
                                    df = pd.DataFrame(transactions)
                                    csv = df.to_csv(index=False)
                                    st.download_button(
                                        label="📊 Download CSV",
                                        data=csv,
                                        file_name="bank_transactions.csv",
                                        mime="text/csv"
                                    )
                            
                            with col_dl3:
                                # Tally XML download
                                if 'tally_xml' in st.session_state:
                                    st.download_button(
                                        label="🔄 Download Tally XML",
                                        data=st.session_state['tally_xml'],
                                        file_name="tally_import.xml",
                                        mime="application/xml"
                                    )
                                else:
                                    st.info("Generate XML first in Tally XML tab")
                            
                            # Instructions for XML import
                            if 'tally_xml' in st.session_state:
                                st.divider()
                                with st.expander("📖 How to import XML into Tally"):
                                    st.markdown("""
                                    ### Steps to import into Tally:
                                    
                                    1. **Open Tally** and select your company
                                    2. **Go to Gateway of Tally** → Import → XML Files
                                    3. **Browse and select** the downloaded XML file
                                    4. **Click Import** to process the transactions
                                    5. **Verify** the imported transactions in your vouchers
                                    
                                    ### Important Notes:
                                    - 🏢 Make sure the company name matches exactly
                                    - 💰 All transactions will be posted to "Suspense" ledger
                                    - ✅ The Suspense ledger will be created automatically if it doesn't exist
                                    - 📝 You can later transfer amounts from Suspense to proper ledgers
                                    - 🔄 Always backup your Tally data before importing
                                    
                                    ### After Import:
                                    - Review transactions in Receipt/Payment vouchers
                                    - Move amounts from Suspense to appropriate ledgers
                                    - Verify running balance matches your bank statement
                                    """)

    # Instructions and tips for bank statements
    with st.expander("📖 How to use Bank Statement Processing"):
        st.markdown("""
        ### Instructions:
        1. **Upload Image**: Select a PNG image of your bank statement
        2. **Extract Data**: Click the "Extract Transactions" button
        3. **Review Results**: Check the extracted transaction data
        4. **Download**: Save the results as JSON or CSV
        
        ### Tips for better results:
        - ✅ Use high-quality, clear images
        - ✅ Ensure good lighting and contrast
        - ✅ Make sure all text is readable
        - ✅ Avoid blurry or rotated images
        - ✅ Include the complete transaction table
        
        ### Supported Data Fields:
        - **Date**: Transaction date
        - **Narration**: Transaction description
        - **Debit Amount**: Money debited from account
        - **Credit Amount**: Money credited to account  
        - **Running Balance**: Account balance after transaction
        """)

def process_invoices(company_name: str, company_state: str | None):
    """Handle invoice processing."""
    st.subheader("📄 Invoice Processing")
    st.markdown("Upload invoice images to extract transaction data and generate purchase/sales vouchers")
    
    if not company_name or not company_state:
        st.warning("⚠️ Please configure company name and state in the settings above")
        return
    
    # Invoice type selection
    invoice_type = st.selectbox(
        "Invoice Type",
        options=["Purchase Invoice", "Sales Invoice"],
        help="Select whether this is a purchase or sales invoice"
    )
    
    # File uploader for invoices
    uploaded_file = st.file_uploader(
        "Choose an invoice file",
        type=['png', 'jpg', 'jpeg', 'pdf'],
        help="Upload a clear image or PDF of your invoice",
        key="invoice_uploader"
    )
    
    if uploaded_file is not None:
        # Convert file to PNG format for processing
        try:
            png_bytes = convert_file_to_png_bytes(uploaded_file)
            original_format = uploaded_file.name.lower().split('.')[-1].upper()
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return
        
        # Display uploaded file
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader(f"📄 Uploaded {original_format} File")
            try:
                display_image = Image.open(io.BytesIO(png_bytes))
                st.image(display_image, caption=f"Invoice ({original_format})", use_column_width=True)
                st.info(f"**File Details:**\n- Original Format: {original_format}\n- Size: {display_image.size[0]} x {display_image.size[1]} pixels")
            except Exception as e:
                st.error(f"Error displaying image: {str(e)}")
                return
        
        with col2:
            st.subheader("🔄 Invoice Data Extraction")
            
            # Check if invoice data is already extracted
            if f'extracted_invoice_{invoice_type}' in st.session_state and st.session_state.get(f'invoice_extraction_completed_{invoice_type}', False):
                invoice_data = st.session_state[f'extracted_invoice_{invoice_type}']
                st.success(f"✅ Invoice data already extracted!")
                if st.button("🔄 Re-extract Invoice Data", type="secondary"):
                    # Clear existing data and re-extract
                    if f'extracted_invoice_{invoice_type}' in st.session_state:
                        del st.session_state[f'extracted_invoice_{invoice_type}']
                    if f'invoice_extraction_completed_{invoice_type}' in st.session_state:
                        del st.session_state[f'invoice_extraction_completed_{invoice_type}']
                    if f'invoice_xml_{invoice_type}' in st.session_state:
                        del st.session_state[f'invoice_xml_{invoice_type}']
                    st.rerun()
            else:
                if st.button("Extract Invoice Data", type="primary"):
                    try:
                        # Show progress
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        status_text.text("🔍 Analyzing invoice...")
                        progress_bar.progress(25)
                        
                        # Get invoice extractor
                        @st.cache_resource
                        def get_invoice_extractor():
                            return InvoiceExtractor()
                        
                        extractor = get_invoice_extractor()
                        
                        status_text.text("🤖 Processing with AI...")
                        progress_bar.progress(50)
                        
                        # Extract invoice data
                        invoice_data = extractor.extract_invoice_data(
                            png_bytes, 
                            invoice_type.replace(' Invoice', '').lower(),
                            company_state
                        )
                        
                        status_text.text("✅ Complete!")
                        progress_bar.progress(100)
                        
                        # Store invoice data in session state
                        st.session_state[f'extracted_invoice_{invoice_type}'] = invoice_data
                        st.session_state[f'invoice_extraction_completed_{invoice_type}'] = True
                        
                        # Clear progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        
                        if invoice_data:
                            st.success(f"🎉 Successfully extracted invoice data!")
                        else:
                            st.warning("⚠️ No invoice data found. Please ensure the image is clear and contains invoice information.")
                            
                    except Exception as e:
                        st.error(f"❌ Error processing invoice: {str(e)}")
        
        # Display extracted invoice data if available
        if f'extracted_invoice_{invoice_type}' in st.session_state and st.session_state.get(f'invoice_extraction_completed_{invoice_type}', False):
            invoice_data = st.session_state[f'extracted_invoice_{invoice_type}']
            
            if invoice_data:
                st.divider()
                st.subheader("📋 Extracted Invoice Data")
                
                # Create tabs for different views
                tab1, tab2, tab3, tab4 = st.tabs(["📊 Invoice Details", "📄 JSON View", "🔄 Tally XML", "💾 Download"])
                
                with tab1:
                    # Display invoice details
                    col_info1, col_info2 = st.columns(2)
                    
                    with col_info1:
                        st.markdown("**Invoice Information:**")
                        st.write(f"Invoice Number: {invoice_data.get('invoice_number', 'N/A')}")
                        st.write(f"Invoice Date: {invoice_data.get('invoice_date', 'N/A')}")
                        
                        if invoice_type == "Purchase Invoice":
                            st.write(f"Vendor: {invoice_data.get('vendor_name', 'N/A')}")
                            st.write(f"Vendor GSTIN: {invoice_data.get('vendor_gstin', 'N/A')}")
                        else:
                            st.write(f"Customer: {invoice_data.get('buyer_name', 'N/A')}")
                            st.write(f"Customer GSTIN: {invoice_data.get('buyer_gstin', 'N/A')}")
                    
                    with col_info2:
                        st.markdown("**Amount Details:**")
                        st.write(f"Taxable Value: ₹{invoice_data.get('total_taxable_value', 0):,.2f}")
                        st.write(f"CGST: ₹{invoice_data.get('total_cgst', 0) or 0:,.2f}")
                        st.write(f"SGST: ₹{invoice_data.get('total_sgst', 0) or 0:,.2f}")
                        st.write(f"IGST: ₹{invoice_data.get('total_igst', 0) or 0:,.2f}")
                        st.write(f"**Total: ₹{invoice_data.get('total_invoice_value', 0):,.2f}**")
                    
                    # Display items
                    if invoice_data.get('items'):
                        st.subheader("📦 Line Items")
                        import pandas as pd
                        items_df = pd.DataFrame(invoice_data['items'])
                        st.dataframe(items_df, use_container_width=True)
                
                with tab2:
                    # Display as JSON
                    json_str = json.dumps(invoice_data, indent=2)
                    st.code(json_str, language="json")
                
                with tab3:
                    # Tally XML Generation
                    st.subheader("🔄 Generate Tally XML")
                    
                    try:
                        # Initialize XML generator
                        xml_generator = InvoiceXMLGenerator(company_name, company_state)
                        
                        if st.button("🔄 Generate Tally XML", type="primary"):
                            with st.spinner("Generating Tally XML..."):
                                if invoice_type == "Purchase Invoice":
                                    xml_content = xml_generator.generate_purchase_xml(invoice_data)
                                else:
                                    xml_content = xml_generator.generate_sales_xml(invoice_data)
                                
                                st.success("✅ Tally XML generated successfully!")
                                
                                # Display XML preview (first 2000 chars)
                                st.subheader("📄 XML Preview")
                                preview_xml = xml_content[:2000]
                                if len(xml_content) > 2000:
                                    preview_xml += "\n... (truncated, full XML available in download)"
                                
                                st.code(preview_xml, language="xml")
                                
                                # Store XML in session state for download
                                st.session_state[f'invoice_xml_{invoice_type}'] = xml_content
                                
                                # Quick info about the XML
                                st.info(f"""
                                **XML Details:**
                                - Invoice Type: {invoice_type}
                                - Company: {company_name}
                                - Items: {len(invoice_data.get('items', []))}
                                - XML Size: {len(xml_content)} characters
                                """)
                                
                    except Exception as e:
                        st.error(f"❌ Error generating XML: {str(e)}")
                
                with tab4:
                    # Download options
                    st.subheader("💾 Download Options")
                    
                    col_dl1, col_dl2, col_dl3 = st.columns(3)
                    
                    with col_dl1:
                        # JSON download
                        json_str = json.dumps(invoice_data, indent=2)
                        st.download_button(
                            label="📄 Download JSON",
                            data=json_str,
                            file_name=f"invoice_{invoice_type.lower().replace(' ', '_')}.json",
                            mime="application/json"
                        )
                    
                    with col_dl2:
                        # CSV download for items
                        if invoice_data.get('items'):
                            import pandas as pd
                            df = pd.DataFrame(invoice_data['items'])
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📊 Download Items CSV",
                                data=csv,
                                file_name=f"invoice_items_{invoice_type.lower().replace(' ', '_')}.csv",
                                mime="text/csv"
                            )
                    
                    with col_dl3:
                        # Tally XML download
                        if f'invoice_xml_{invoice_type}' in st.session_state:
                            st.download_button(
                                label="🔄 Download Tally XML",
                                data=st.session_state[f'invoice_xml_{invoice_type}'],
                                file_name=f"tally_{invoice_type.lower().replace(' ', '_')}.xml",
                                mime="application/xml"
                            )
                        else:
                            st.info("Generate XML first in Tally XML tab")
    
    # Instructions
    with st.expander("📖 How to use Invoice Processing"):
        st.markdown("""
        ### Instructions:
        1. **Select Type**: Choose Purchase or Sales invoice
        2. **Upload Image**: Select a clear image of your invoice
        3. **Extract Data**: Click "Extract Invoice Data" button
        4. **Review Results**: Check the extracted invoice details and items
        5. **Generate XML**: Create Tally-compatible XML for import
        6. **Download**: Save the results as JSON, CSV, or XML
        
        ### Features:
        - ✅ AI-powered invoice data extraction
        - ✅ Automatic GST calculation and bifurcation
        - ✅ Vendor/customer master creation in XML
        - ✅ Item-wise tax calculation
        - ✅ Purchase/Sales voucher XML generation
        - ✅ Descriptive ledger naming (Purchase - Item, Input CGST 18%, etc.)
        
        ### Tips for better results:
        - ✅ Use high-quality, clear images
        - ✅ Ensure all text is readable
        - ✅ Include complete invoice with all line items
        - ✅ Make sure GST details are visible
        """)

def process_gst_returns(company_name: str, company_state: str | None):
    """Handle GST return JSON processing."""
    st.subheader("📊 GST Return Processing")
    st.markdown("Process GST returns: Upload JSON files to generate Tally XML or create GSTR1 upload files from sales invoices")
    
    if not company_name or not company_state:
        st.warning("⚠️ Please configure company name and state in the settings above")
        return
    
    # Company GSTIN input
    company_gstin = st.text_input(
        "Company GSTIN",
        placeholder="Enter your company's GSTIN (15 digits)",
        help="Required for GST portal JSON generation and processing",
        key="company_gstin_input"
    )
    
    if company_gstin and len(company_gstin) != 15:
        st.warning("⚠️ GSTIN should be exactly 15 characters")
    
    # Create tabs for different GST processing options
    tab_upload, tab_create_gstr1, tab_gstr2b_dedicated, tab_bulk_process = st.tabs([
        "📥 Upload GST JSON to Tally", 
        "📤 Create GSTR1 from Sales Invoices", 
        "🏛️ GSTR2B Dedicated Processor",
        "🔄 Bulk Process GST Data"
    ])
    
    with tab_upload:
        st.subheader("📥 GST Portal JSON to Tally XML")
        st.markdown("Upload downloaded GST portal JSON files (GSTR1, GSTR2A, GSTR2B) to generate Tally import XML")
        
        # GST return type selection
        gst_return_type = st.selectbox(
            "GST Return Type",
            options=["GSTR1 (Sales)", "GSTR2A (Purchase)", "GSTR2B (Purchase)", "GSTR3B (Monthly Return)"],
            help="Select the type of GST return you want to process"
        )
        
        # File uploader for GST JSON
        uploaded_gst_file = st.file_uploader(
            "Upload GST Return JSON File",
            type=['json'],
            help="Upload the JSON file downloaded from GST portal",
            key="gst_json_uploader"
        )
        
        if uploaded_gst_file is not None:
            try:
                # Read and parse JSON
                json_content = uploaded_gst_file.read().decode('utf-8')
                gst_data = json.loads(json_content)
                
                st.success(f"✅ {gst_return_type} JSON file loaded successfully!")
                
                # Display file info
                st.info(f"""
                **File Details:**
                - File Name: {uploaded_gst_file.name}
                - File Size: {len(json_content)} characters
                - Return Type: {gst_return_type}
                - GSTIN: {gst_data.get('gstin', 'Not found')}
                - Period: {gst_data.get('ret_period', gst_data.get('fp', 'Not found'))}
                """)
                
                # Generate Tally XML
                if st.button("🔄 Generate Tally XML from GST Data", type="primary"):
                    if not company_gstin:
                        st.error("❌ Please enter your company GSTIN first")
                    else:
                        try:
                            with st.spinner("Generating Tally XML from GST data..."):
                                # Initialize GST XML generator
                                gst_xml_generator = GSTTallyXMLGenerator(company_name, company_state)
                                
                                # Generate XML based on return type
                                if "GSTR1" in gst_return_type:
                                    xml_content = gst_xml_generator.generate_gstr1_xml(gst_data)
                                    xml_type = "Sales"
                                elif "GSTR2A" in gst_return_type:
                                    xml_content = gst_xml_generator.generate_gstr2a_xml(gst_data)
                                    xml_type = "Purchase"
                                elif "GSTR2B" in gst_return_type:
                                    xml_content = gst_xml_generator.generate_gstr2b_xml(gst_data)
                                    xml_type = "Purchase"
                                else:
                                    st.error(f"❌ {gst_return_type} processing not yet implemented")
                                    return
                                
                                st.success("✅ Tally XML generated successfully!")
                                
                                # Display XML preview
                                st.subheader("📄 XML Preview")
                                preview_xml = xml_content[:2000]
                                if len(xml_content) > 2000:
                                    preview_xml += "\n... (truncated, full XML available in download)"
                                
                                st.code(preview_xml, language="xml")
                                
                                # Store XML for download
                                st.session_state['gst_tally_xml'] = xml_content
                                
                                # Download button
                                st.download_button(
                                    label="💾 Download Tally XML",
                                    data=xml_content,
                                    file_name=f"tally_{gst_return_type.lower().replace(' ', '_').replace('(', '').replace(')', '')}.xml",
                                    mime="application/xml"
                                )
                                
                        except Exception as e:
                            st.error(f"❌ Error generating XML: {str(e)}")
                
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON file: {str(e)}")
            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
    
    with tab_create_gstr1:
        st.subheader("📤 Create GSTR1 JSON from Sales Invoices")
        st.markdown("Generate GST portal uploadable JSON file for GSTR1 from your processed sales invoices")
        
        if not company_gstin:
            st.warning("⚠️ Please enter your company GSTIN above first")
        else:
            # Period selection
            col_month, col_year = st.columns(2)
            with col_month:
                return_month = st.selectbox(
                    "Return Month",
                    options=[f"{i:02d}" for i in range(1, 13)],
                    format_func=lambda x: datetime.strptime(x, "%m").strftime("%B"),
                    help="Select the month for GSTR1"
                )
            
            with col_year:
                current_year = datetime.now().year
                return_year = st.selectbox(
                    "Return Year",
                    options=[str(year) for year in range(current_year-2, current_year+1)],
                    index=2,  # Default to current year
                    help="Select the year for GSTR1"
                )
            
            # Check for sales invoices in session state
            sales_invoices = []
            if 'extracted_invoice_Sales Invoice' in st.session_state:
                sales_invoices.append(st.session_state['extracted_invoice_Sales Invoice'])
            
            # File uploader for multiple sales invoices JSON
            uploaded_sales_files = st.file_uploader(
                "Upload Sales Invoice JSON Files (Optional)",
                type=['json'],
                accept_multiple_files=True,
                help="Upload JSON files of processed sales invoices to include in GSTR1",
                key="sales_json_uploader"
            )
            
            if uploaded_sales_files:
                try:
                    for file in uploaded_sales_files:
                        json_content = file.read().decode('utf-8')
                        invoice_data = json.loads(json_content)
                        if invoice_data.get('invoice_type') == 'sales':
                            sales_invoices.append(invoice_data)
                    
                    st.success(f"✅ Loaded {len(uploaded_sales_files)} sales invoice files")
                except Exception as e:
                    st.error(f"❌ Error loading sales invoice files: {str(e)}")
            
            if sales_invoices:
                st.info(f"📋 Found {len(sales_invoices)} sales invoices for GSTR1 generation")
                
                if st.button("🔄 Generate GSTR1 JSON", type="primary"):
                    try:
                        with st.spinner("Generating GSTR1 JSON..."):
                            # Initialize GSTR1 generator
                            gstr1_generator = GSTPortalJSONGenerator(company_gstin, company_state)
                            
                            # Generate GSTR1 JSON
                            gstr1_data = gstr1_generator.generate_gstr1_json(
                                sales_invoices, return_month, return_year
                            )
                            
                            # Validate data
                            validation_result = gstr1_generator.validate_gstr1_data(gstr1_data)
                            
                            if validation_result['valid']:
                                st.success("✅ GSTR1 JSON generated successfully!")
                                
                                # Display summary
                                st.subheader("📊 GSTR1 Summary")
                                col_sum1, col_sum2, col_sum3 = st.columns(3)
                                
                                with col_sum1:
                                    st.metric("B2B Customers", len(gstr1_data.get('b2b', [])))
                                with col_sum2:
                                    st.metric("B2CL Invoices", len(gstr1_data.get('b2cl', [])))
                                with col_sum3:
                                    st.metric("B2CS Entries", len(gstr1_data.get('b2cs', [])))
                                
                                # Show HSN summary
                                hsn_data = gstr1_data.get('hsn', {}).get('data', [])
                                if hsn_data:
                                    st.subheader("📦 HSN Summary")
                                    import pandas as pd
                                    hsn_df = pd.DataFrame(hsn_data)
                                    st.dataframe(hsn_df, use_container_width=True)
                                
                                # JSON preview
                                st.subheader("📄 GSTR1 JSON Preview")
                                json_str = json.dumps(gstr1_data, indent=2)
                                preview_json = json_str[:2000]
                                if len(json_str) > 2000:
                                    preview_json += "\n... (truncated, full JSON available in download)"
                                
                                st.code(preview_json, language="json")
                                
                                # Download button
                                st.download_button(
                                    label="💾 Download GSTR1 JSON",
                                    data=json_str,
                                    file_name=f"GSTR1_{company_gstin}_{return_month}{return_year}.json",
                                    mime="application/json"
                                )
                                
                                # Show validation warnings
                                if validation_result['warnings']:
                                    with st.expander("⚠️ Validation Warnings"):
                                        for warning in validation_result['warnings']:
                                            st.warning(warning)
                            
                            else:
                                st.error("❌ GSTR1 validation failed:")
                                for error in validation_result['errors']:
                                    st.error(f"• {error}")
                                
                    except Exception as e:
                        st.error(f"❌ Error generating GSTR1: {str(e)}")
            
            else:
                st.info("💡 No sales invoices found. Process some sales invoices first or upload sales invoice JSON files.")
    
    with tab_gstr2b_dedicated:
        process_gstr2b_dedicated(company_name, company_state, company_gstin)
    
    with tab_bulk_process:
        st.subheader("🔄 Bulk Process GST Data")
        st.markdown("Advanced processing for multiple GST files and bulk operations")
        
        # Placeholder for bulk processing features
        st.info("🔮 Advanced bulk processing features coming soon:")
        st.markdown("""
        **Planned Features:**
        - 📁 Bulk upload multiple GST return files
        - 🔄 Batch conversion to Tally XML
        - 📊 Consolidated GST analysis and reports
        - 🔍 Data validation and error checking
        - 📈 GST compliance reports
        - 💾 Bulk download processed files
        """)
    
    # Instructions
    with st.expander("📖 How to use GST Return Processing"):
        st.markdown("""
        ### 📥 Upload GST JSON to Tally:
        1. **Download** your GST return JSON from GST portal
        2. **Select** the appropriate return type (GSTR1, GSTR2A, GSTR2B)
        3. **Upload** the JSON file
        4. **Generate** Tally XML for direct import
        
        ### 📤 Create GSTR1 from Sales Invoices:
        1. **Enter** your company GSTIN and select return period
        2. **Upload** processed sales invoice JSON files
        3. **Generate** GSTR1 JSON for portal upload
        4. **Validate** and download the file
        
        ### Features:
        - ✅ Convert GST portal JSON to Tally XML
        - ✅ Generate GSTR1 from sales invoices
        - ✅ Automatic GST bifurcation (CGST+SGST vs IGST)
        - ✅ Smart party and ledger creation
        - ✅ Data validation and error checking
        - ✅ HSN-wise summary for GSTR1
        - ✅ B2B, B2CL, B2CS categorization
        
        ### Supported Formats:
        - **Input**: GST portal JSON files, Sales invoice JSON
        - **Output**: Tally XML, GSTR1 JSON for portal upload
        """)
    
    # GST Portal Offline JSON Generator
    st.divider()
    st.markdown("### 🔧 GST Portal Offline Utility")
    st.markdown("Create JSON files for uploading to GST portal (offline utility tool)")
    
    with st.expander("📤 Generate GSTR1 JSON for GST Portal Upload"):
        st.markdown("**Create GSTR1 JSON file for outward supplies to upload on GST portal**")
        
        # Invoice entry form
        st.subheader("Invoice Details Entry")
        col1, col2 = st.columns(2)
        
        with col1:
            customer_gstin = st.text_input("Customer GSTIN", placeholder="01ABCDE1234F1Z5")
            invoice_number = st.text_input("Invoice Number", placeholder="INV001")
            invoice_date = st.date_input("Invoice Date")
        
        with col2:
            place_of_supply = st.selectbox("Place of Supply", 
                options=["01-Jammu and Kashmir", "02-Himachal Pradesh", "03-Punjab", "04-Chandigarh", 
                        "05-Uttarakhand", "06-Haryana", "07-Delhi", "08-Rajasthan", "09-Uttar Pradesh",
                        "10-Bihar", "11-Sikkim", "12-Arunachal Pradesh", "13-Nagaland", "14-Manipur",
                        "15-Mizoram", "16-Tripura", "17-Meghalaya", "18-Assam", "19-West Bengal",
                        "20-Jharkhand", "21-Odisha", "22-Chhattisgarh", "23-Madhya Pradesh",
                        "24-Gujarat", "25-Daman and Diu", "26-Dadra and Nagar Haveli", "27-Maharashtra",
                        "28-Andhra Pradesh", "29-Karnataka", "30-Goa", "31-Lakshadweep", "32-Kerala",
                        "33-Tamil Nadu", "34-Puducherry", "35-Andaman and Nicobar Islands", "36-Telangana",
                        "37-Andhra Pradesh"],
                help="Select place of supply for the transaction")
            
            tax_rate = st.selectbox("Tax Rate (%)", options=[0, 5, 12, 18, 28])
            taxable_value = st.number_input("Taxable Value (₹)", min_value=0.0, format="%.2f")
        
        if st.button("Add to GSTR1 JSON", type="primary"):
            if customer_gstin and invoice_number and taxable_value > 0:
                # Create GSTR1 JSON structure
                pos_code = place_of_supply.split('-')[0]
                gst_processor = GSTProcessor(company_state)
                company_state_code = next((code for state, code in gst_processor.state_codes.items() if state == company_state), "27")
                
                # Calculate tax amounts
                is_interstate = pos_code != company_state_code
                if is_interstate:
                    igst_amount = (taxable_value * tax_rate) / 100
                    cgst_amount = 0
                    sgst_amount = 0
                else:
                    igst_amount = 0
                    cgst_amount = (taxable_value * tax_rate) / 200  # Half of total tax
                    sgst_amount = (taxable_value * tax_rate) / 200  # Half of total tax
                
                total_value = taxable_value + igst_amount + cgst_amount + sgst_amount
                
                gstr1_json = {
                    "version": "GST1.1",
                    "hash": "auto_generated_hash",
                    "gstin": f"{company_state_code}ABCDE1234F1Z5",  # Placeholder GSTIN
                    "fp": invoice_date.strftime("%m%Y"),
                    "b2b": [
                        {
                            "ctin": customer_gstin,
                            "inv": [
                                {
                                    "inum": invoice_number,
                                    "idt": invoice_date.strftime("%d-%m-%Y"),
                                    "val": round(total_value, 2),
                                    "pos": pos_code,
                                    "rchrg": "N",
                                    "etin": "",
                                    "inv_typ": "R",
                                    "itms": [
                                        {
                                            "num": 1,
                                            "itm_det": {
                                                "rt": tax_rate,
                                                "txval": round(taxable_value, 2),
                                                "iamt": round(igst_amount, 2),
                                                "camt": round(cgst_amount, 2),
                                                "samt": round(sgst_amount, 2),
                                                "csamt": 0
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                    "b2cs": [],
                    "hsn": [],
                    "doc_issue": {}
                }
                
                st.success("✅ GSTR1 JSON created successfully!")
                
                # Display JSON preview
                st.subheader("📄 Generated JSON Preview")
                st.code(json.dumps(gstr1_json, indent=2), language="json")
                
                # Download button
                json_str = json.dumps(gstr1_json, indent=2)
                st.download_button(
                    label="📥 Download GSTR1 JSON for GST Portal",
                    data=json_str,
                    file_name=f"GSTR1_{invoice_date.strftime('%m%Y')}_{invoice_number}.json",
                    mime="application/json"
                )
                
                st.info("""
                **How to use this JSON file:**
                1. Download the JSON file
                2. Login to GST Portal → Returns Dashboard
                3. Select GSTR-1 → Upload JSON File
                4. Browse and select this downloaded file
                5. Review and submit your return
                """)
            else:
                st.error("⚠️ Please fill all required fields with valid data")
    
    # Instructions
    with st.expander("📖 How to use GST Return Processing"):
        st.markdown("""
        ### Features:
        - ⚡ **Ultra-fast processing**: JSON parsing in milliseconds
        - 📊 **Bulk transactions**: Process hundreds of transactions at once
        - 🧠 **Smart ledger naming**: "Input IGST 18%", "Local Purchase 28%"
        - 🏢 **Auto party creation**: Extract vendor/customer from GSTIN
        - 🗺️ **State-based logic**: Automatic CGST+SGST vs IGST determination
        
        ### How to use:
        1. Download JSON files from GST portal (GSTR2B/1/2A)
        2. Select the correct return type above
        3. Upload the JSON files
        4. Review the extracted transactions and ledger names
        5. XML generation coming soon!
        
        ### Supported Returns:
        - **GSTR2B**: Purchase transactions with input tax credit
        - **GSTR1**: Sales transactions with output tax
        - **GSTR2A**: Purchase transactions (auto-matched)
        """)

def process_gstr2b_dedicated(company_name: str, company_state: str | None, company_gstin: str | None):
    """Handle dedicated GSTR2B processing with separate Masters and Transactions XML generation."""
    st.subheader("🏛️ GSTR2B Dedicated Processor")
    st.markdown("Upload official GSTR2B JSON from GST portal to generate separate Masters and Transactions XML files for Tally")
    
    if not company_name or not company_state:
        st.warning("⚠️ Please configure company name and state in the main settings above")
        return
    
    if not company_gstin:
        st.warning("⚠️ Please enter your company GSTIN in the GST section above")
        return
    
    # File uploader for GSTR2B JSON
    st.subheader("📥 Upload GSTR2B JSON File")
    uploaded_gstr2b_file = st.file_uploader(
        "Choose GSTR2B JSON file from GST portal",
        type=['json'],
        help="Upload the official GSTR2B JSON file downloaded from GST portal",
        key="gstr2b_dedicated_uploader"
    )
    
    if uploaded_gstr2b_file is not None:
        try:
            # Read and parse JSON
            json_content = uploaded_gstr2b_file.read().decode('utf-8')
            gstr2b_data = json.loads(json_content)
            
            st.success(f"✅ GSTR2B JSON file loaded successfully!")
            
            # Display basic file info
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"""
                **File Details:**
                - File Name: {uploaded_gstr2b_file.name}
                - File Size: {len(json_content):,} characters
                - Data Structure: Official GST Portal Format
                """)
            
            with col2:
                # Extract and display metadata
                data = gstr2b_data.get('data', {})
                metadata_info = f"""
                **GSTR2B Details:**
                - GSTIN: {data.get('gstin', 'Not found')}
                - Return Period: {data.get('rtnprd', 'Not found')}
                - Generated Date: {data.get('gendt', 'Not found')}
                - Version: {data.get('version', 'Not found')}
                """
                st.info(metadata_info)
            
            # Validate GSTR2B data
            processor = GSTR2BDedicatedProcessor(company_state)
            validation_result = processor.validate_gstr2b_data(gstr2b_data)
            
            if validation_result['valid']:
                st.success("✅ GSTR2B JSON structure is valid")
                
                if validation_result['warnings']:
                    with st.expander("⚠️ Validation Notes"):
                        for warning in validation_result['warnings']:
                            st.warning(warning)
                
                # Process GSTR2B data
                if st.button("🔄 Process GSTR2B Data", type="primary"):
                    with st.spinner("Processing GSTR2B data..."):
                        vendors, invoices, metadata = processor.process_gstr2b_json(gstr2b_data)
                        
                        if vendors and invoices:
                            # Store in session state
                            st.session_state['gstr2b_vendors'] = vendors
                            st.session_state['gstr2b_invoices'] = invoices  
                            st.session_state['gstr2b_metadata'] = metadata
                            st.session_state['gstr2b_processed'] = True
                            
                            st.success(f"🎉 Successfully processed {len(vendors)} vendors with {len(invoices)} invoices!")
                        else:
                            st.error("❌ No data could be processed from the GSTR2B file")
                
            else:
                st.error("❌ GSTR2B JSON validation failed:")
                for error in validation_result['errors']:
                    st.error(f"• {error}")
                
        except json.JSONDecodeError as e:
            st.error(f"❌ Invalid JSON file: {str(e)}")
        except Exception as e:
            st.error(f"❌ Error processing GSTR2B file: {str(e)}")
    
    # Display processed data and XML generation options
    if st.session_state.get('gstr2b_processed', False):
        vendors = st.session_state.get('gstr2b_vendors', [])
        invoices = st.session_state.get('gstr2b_invoices', [])
        metadata = st.session_state.get('gstr2b_metadata', {})
        
        st.divider()
        st.subheader("📊 Processed GSTR2B Data")
        
        # Summary statistics
        processor = GSTR2BDedicatedProcessor(company_state)
        summary = processor.get_vendor_summary(vendors)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Vendors", summary.get('total_vendors', 0))
        with col2:
            st.metric("Total Invoices", summary.get('total_invoices', 0))
        with col3:
            st.metric("Total Taxable Value", f"₹{summary.get('total_taxable_value', 0):,.2f}")
        with col4:
            st.metric("Total Tax Amount", f"₹{summary.get('total_tax_amount', 0):,.2f}")
        
        # Create tabs for data view and XML generation
        tab_vendors, tab_invoices, tab_xml_generation = st.tabs(["👥 Vendors", "📄 Invoices", "🔄 Generate XML"])
        
        with tab_vendors:
            st.subheader("👥 Vendor Summary")
            vendor_data = []
            for vendor in vendors:
                vendor_data.append({
                    'GSTIN': vendor.ctin,
                    'Vendor Name': vendor.trdnm,
                    'Invoices': vendor.total_invoices,
                    'Taxable Value': f"₹{vendor.total_taxable_value:,.2f}",
                    'CGST': f"₹{vendor.total_cgst:,.2f}",
                    'SGST': f"₹{vendor.total_sgst:,.2f}",
                    'IGST': f"₹{vendor.total_igst:,.2f}",
                    'Total Tax': f"₹{vendor.total_cgst + vendor.total_sgst + vendor.total_igst:,.2f}"
                })
            
            import pandas as pd
            if vendor_data:
                df_vendors = pd.DataFrame(vendor_data)
                st.dataframe(df_vendors, use_container_width=True)
        
        with tab_invoices:
            st.subheader("📄 Invoice Details")
            invoice_data = []
            for invoice in invoices[:100]:  # Show first 100 invoices
                invoice_data.append({
                    'Vendor': invoice.vendor_name[:30] + '...' if len(invoice.vendor_name) > 30 else invoice.vendor_name,
                    'Invoice No': invoice.invoice_number,
                    'Date': invoice.invoice_date,
                    'Value': f"₹{invoice.invoice_value:,.2f}",
                    'CGST': f"₹{invoice.cgst_amount:,.2f}",
                    'SGST': f"₹{invoice.sgst_amount:,.2f}",
                    'IGST': f"₹{invoice.igst_amount:,.2f}"
                })
            
            if invoice_data:
                df_invoices = pd.DataFrame(invoice_data)
                st.dataframe(df_invoices, use_container_width=True)
                if len(invoices) > 100:
                    st.info(f"Showing first 100 invoices out of {len(invoices)} total")
        
        with tab_xml_generation:
            st.subheader("🔄 Generate Tally XML Files")
            st.markdown("Generate separate Masters and Transactions XML files for import into Tally")
            
            # Masters XML Generation
            st.markdown("### 👥 Masters XML (Vendor Ledgers)")
            masters_generator = GSTR2BMastersXMLGenerator(company_name, company_state)
            masters_validation = masters_generator.validate_masters_xml(vendors)
            
            if masters_validation['valid']:
                st.success(f"✅ Ready to generate Masters XML for {masters_validation['summary']['total_vendors']} vendors")
                
                if st.button("🔄 Generate Masters XML", type="primary"):
                    with st.spinner("Generating Masters XML..."):
                        masters_xml = masters_generator.generate_masters_xml(vendors, metadata)
                        if masters_xml:
                            st.session_state['gstr2b_masters_xml'] = masters_xml
                            st.success("✅ Masters XML generated successfully!")
                        else:
                            st.error("❌ Failed to generate Masters XML")
            else:
                st.error("❌ Masters XML validation failed:")
                for error in masters_validation['errors']:
                    st.error(f"• {error}")
            
            # Transactions XML Generation  
            st.markdown("### 📄 Transactions XML (Purchase Vouchers)")
            transactions_generator = GSTR2BTransactionsXMLGenerator(company_name, company_state)
            transactions_validation = transactions_generator.validate_transactions_xml(invoices)
            
            if transactions_validation['valid']:
                summary = transactions_validation['summary']
                st.success(f"✅ Ready to generate Transactions XML for {summary['total_invoices']} invoices")
                st.info(f"📊 Interstate: {summary['interstate_invoices']}, Intrastate: {summary['intrastate_invoices']}")
                
                if st.button("🔄 Generate Transactions XML", type="primary"):
                    with st.spinner("Generating Transactions XML..."):
                        transactions_xml = transactions_generator.generate_transactions_xml(invoices, metadata)
                        if transactions_xml:
                            st.session_state['gstr2b_transactions_xml'] = transactions_xml
                            st.success("✅ Transactions XML generated successfully!")
                        else:
                            st.error("❌ Failed to generate Transactions XML")
            else:
                st.error("❌ Transactions XML validation failed:")
                for error in transactions_validation['errors']:
                    st.error(f"• {error}")
            
            # Download section
            st.divider()
            st.subheader("💾 Download XML Files")
            
            col_download1, col_download2 = st.columns(2)
            
            with col_download1:
                if 'gstr2b_masters_xml' in st.session_state:
                    st.download_button(
                        label="📥 Download Masters XML",
                        data=st.session_state['gstr2b_masters_xml'],
                        file_name=f"GSTR2B_Masters_{metadata.get('gstin', 'Unknown')}_{metadata.get('return_period', 'Unknown')}.xml",
                        mime="application/xml"
                    )
                else:
                    st.info("Generate Masters XML first")
            
            with col_download2:
                if 'gstr2b_transactions_xml' in st.session_state:
                    st.download_button(
                        label="📥 Download Transactions XML",
                        data=st.session_state['gstr2b_transactions_xml'],
                        file_name=f"GSTR2B_Transactions_{metadata.get('gstin', 'Unknown')}_{metadata.get('return_period', 'Unknown')}.xml",
                        mime="application/xml"
                    )
                else:
                    st.info("Generate Transactions XML first")
            
            # Import instructions
            if 'gstr2b_masters_xml' in st.session_state or 'gstr2b_transactions_xml' in st.session_state:
                with st.expander("📖 How to Import XML into Tally"):
                    st.markdown("""
                    ### Import Order:
                    1. **First import Masters XML** - This creates all vendor ledgers and tax ledgers
                    2. **Then import Transactions XML** - This creates all purchase vouchers
                    
                    ### Steps for each XML import:
                    1. Open Tally and select your company
                    2. Go to **Gateway of Tally → Import → XML Files**
                    3. Browse and select the XML file
                    4. Click **Import** to process
                    5. Verify the imported data in vouchers/ledgers
                    
                    ### Important Notes:
                    - 🏢 Company name must match exactly in Tally
                    - 👥 All vendor ledgers will be created under "GSTR2B Suppliers"
                    - 🧾 All tax ledgers will be created under "GST Input Tax"
                    - 💰 Purchase vouchers will reference the invoice numbers
                    - 🔄 Always backup your Tally data before importing
                    """)
    
    # Instructions
    with st.expander("📖 How to use GSTR2B Dedicated Processor"):
        st.markdown("""
        ### Instructions:
        1. **Download** GSTR2B JSON from GST portal (View Inward Supplies → Download JSON)
        2. **Configure** company details and GSTIN above
        3. **Upload** the official GSTR2B JSON file
        4. **Process** the data to extract vendors and invoices
        5. **Generate** separate Masters and Transactions XML files
        6. **Import** XML files into Tally (Masters first, then Transactions)
        
        ### Features:
        - ✅ Official GST portal JSON format support
        - ✅ Separate Masters XML (vendors and tax ledgers)
        - ✅ Separate Transactions XML (purchase vouchers)
        - ✅ Automatic interstate/intrastate detection
        - ✅ GST bifurcation (CGST+SGST vs IGST)
        - ✅ Complete vendor master creation with GSTIN
        - ✅ Proper tax ledger structure for Tally
        
        ### Benefits:
        - 🎯 **Clean Import**: Masters and transactions are separate
        - 📊 **Complete Data**: All vendor details and tax breakups
        - 🔄 **Tally Ready**: XML format optimized for Tally import
        - ✅ **Validated**: Data validation before XML generation
        """)

if __name__ == "__main__":
    main()
