import streamlit as st
import pandas as pd
import io
from fpdf import FPDF
from supabase import create_client, Client

# --- PDF Generation Function ---
def generate_pdf(active_mix, total_kg, total_cost, total_dm, total_cp, actual_concentrate):
    pdf = FPDF()
    pdf.add_page()
    
    # Font fixed to Arial
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Virbac Custom Feed Mix Report", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(50, 8, "Ingredient", 1)
    pdf.cell(40, 8, "Category", 1)
    pdf.cell(30, 8, "Amount (kg)", 1)
    pdf.cell(30, 8, "Price/kg", 1)
    pdf.cell(30, 8, "Cost", 1)
    pdf.ln()
    
    # Table Rows
    pdf.set_font("Arial", size=10)
    for _, row in active_mix.iterrows():
        pdf.cell(50, 8, str(row['name'])[:20], 1)
        pdf.cell(40, 8, str(row['category'])[:15], 1)
        pdf.cell(30, 8, f"{row['quantity_kg']:.2f}", 1)
        pdf.cell(30, 8, f"Rs {row['price_per_kg']:.2f}", 1)
        pdf.cell(30, 8, f"Rs {(row['quantity_kg'] * row['price_per_kg']):.2f}", 1)
        pdf.ln()
        
    pdf.ln(10)
    
    # Summary Metrics
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Final Nutritional Value & Cost:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, txt=f"Total Weight: {total_kg:.2f} kg", ln=True)
    pdf.cell(200, 8, txt=f"Total Cost: Rs {total_cost:.2f}", ln=True)
    pdf.cell(200, 8, txt=f"Total Dry Matter (DM): {total_dm:.2f} kg", ln=True)
    pdf.cell(200, 8, txt=f"Total Crude Protein (CP): {total_cp:.2f} kg", ln=True)
    pdf.cell(200, 8, txt=f"Total Concentrate: {actual_concentrate:.2f} kg", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 1. Page Settings & UI Header ---
st.set_page_config(page_title="Virbac Feed Calculator", page_icon="🐄", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div[data-testid="stMetric"] { background-color: white; border-left: 5px solid #004b87; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    h3 { color: #004b87; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; margin-top: 30px; }
    
    /* Hide the default Streamlit CSV download button on tables */
    [data-testid="stElementToolbar"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# --- Logo & Title ---
col1, col2 = st.columns([1, 4])
with col1:
    st.markdown('<img src="https://in.virbac.com/assets/virbac/build/images/virbac-logo.03fd5e40.svg" width="180">', unsafe_allow_html=True)
with col2:
    st.title("Advanced Feed Calculator")
st.write("---")

# --- 2. Database Connection ---
SUPABASE_URL = "https://obkvdijgkqgsialqpcmf.supabase.co"
SUPABASE_KEY = "sb_secret_kqVDf-aBktlkX9Jg20mKnQ_KSMq4E8M"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# SECTION 1: ANIMAL PROFILE
# ==========================================
st.markdown("### 1. Animal Profile")
col1, col2, col3 = st.columns(3)
with col1:
    breed = st.selectbox("Breed / Category", ["HF / Crossbred", "Jersey", "Buffalo", "Indigenous / Zebu"])
    lactation = st.selectbox("Lactation Number", ["1st (Growing)", "2nd", "3rd or more (Mature)"])
with col2:
    body_weight = st.number_input("Body Weight (kg)", min_value=200, max_value=800, value=400, step=10)
    fat_pct = st.number_input("Milk Fat %", min_value=2.0, max_value=10.0, value=4.0, step=0.1)
with col3:
    milk_yield = st.number_input("Milk Production (Liters/day)", min_value=0, max_value=60, value=15, step=1)
    is_pregnant = st.checkbox("Pregnant (Last 2 months)?")
    
# --- Dynamic Calculation Engine ---
dmi_target = (body_weight * 0.02) + (milk_yield * 0.3)
if breed == "Buffalo": dmi_target *= 1.1 

cp_maintenance = body_weight * 0.003
cp_milk = milk_yield * (0.08 + (fat_pct * 0.01)) 
cp_target_kg = cp_maintenance + cp_milk
cp_target_pct = (cp_target_kg / dmi_target) * 100

tdn_target_kg = (body_weight * 0.01) + (milk_yield * 0.35)
tdn_target_pct = (tdn_target_kg / dmi_target) * 100
fibre_target_pct = 28.0

if breed == "Buffalo":
    maint_conc = 2.0 
    milk_conc = milk_yield * 0.5 
else:
    maint_conc = 1.5 
    milk_conc = milk_yield * 0.4 

preg_conc = 2.0 if is_pregnant else 0.0
total_concentrate_target = maint_conc + milk_conc + preg_conc

# ==========================================
# SECTION 2: CALCULATED REQUIREMENTS
# ==========================================
st.markdown("### 2. Calculated Daily Requirements")
r1, r2, r3, r4, r5 = st.columns(5)
r1.metric("Dry Matter (DMI)", f"{dmi_target:.2f} kg")
r2.metric("Protein (CP)", f"{cp_target_kg:.2f} kg", f"{cp_target_pct:.1f}% DM")
r3.metric("Energy (TDN)", f"{tdn_target_kg:.2f} kg", f"{tdn_target_pct:.1f}% DM")
r4.metric("Min. Fibre", f"{fibre_target_pct:.1f}%")
r5.metric("Target Concentrate", f"{total_concentrate_target:.2f} kg", "NDDB Standard")

# ==========================================
# SECTION 3: MANUAL CALCULATOR
# ==========================================
st.markdown("### 3. Manually Adjust Quantities")

res = supabase.table("Feed Ingredients").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    df["quantity_kg"] = 0.0
    
    edited_df = st.data_editor(
        df[["name", "category", "price_per_kg", "dry_matter", "crude_protein", "quantity_kg"]],
        disabled=["name", "category", "dry_matter", "crude_protein"],
        hide_index=True,
        use_container_width=True
    )
    
    active_mix = edited_df[edited_df["quantity_kg"] > 0]
    
    if not active_mix.empty:
        total_kg = active_mix["quantity_kg"].sum()
        total_cost = (active_mix["quantity_kg"] * active_mix["price_per_kg"]).sum()
        total_dm = (active_mix["quantity_kg"] * active_mix["dry_matter"] / 100).sum()
        total_cp = (active_mix["quantity_kg"] * active_mix["crude_protein"] / 100).sum()
        
        # Calculate how much of the mix is "Concentrate" category
        actual_concentrate = active_mix[active_mix['category'].str.contains('Concentrate', case=False, na=False)]['quantity_kg'].sum()
        
        dm_diff = total_dm - dmi_target
        cp_diff = total_cp - cp_target_kg
        conc_diff = actual_concentrate - total_concentrate_target
        
        st.markdown("#### Your Custom Mix Results:")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Weight", f"{total_kg:.2f} kg")
        col2.metric("Total Cost", f"₹{total_cost:.2f}")
        col3.metric("Actual DM", f"{total_dm:.2f} kg", f"{dm_diff:+.2f} kg from target", delta_color="off")
        col4.metric("Actual CP", f"{total_cp:.2f} kg", f"{cp_diff:+.2f} kg from target", delta_color="off")
        col5.metric("Actual Concentrate", f"{actual_concentrate:.2f} kg", f"{conc_diff:+.2f} kg from NDDB target", delta_color="off")
        
        # --- EXPORT BUTTONS ---
        st.write("---")
        st.markdown("#### Export Report")
        
        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        
        # Excel Export
        with btn_col1:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                active_mix.to_excel(writer, index=False, sheet_name='Feed Mix')
            
            st.download_button(
                label="📊 Download Excel",
                data=buffer.getvalue(),
                file_name="Virbac_Feed_Mix.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        # PDF Export
        with btn_col2:
            pdf_data = generate_pdf(active_mix, total_kg, total_cost, total_dm, total_cp, actual_concentrate)
            st.download_button(
                label="📄 Download PDF",
                data=pdf_data,
                file_name="Virbac_Feed_Mix.pdf",
                mime="application/pdf"
            )
else:
    st.warning("No ingredients found in the database. Please add some first.")
