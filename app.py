import streamlit as st
import pandas as pd
import numpy_financial as npf

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Property Investment Calculator", layout="wide")

st.title("🏠 Advanced Property Investment Calculator")
st.markdown("Adjust the inputs in the sidebar to see real-time returns and sensitivity analysis.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Property & Loan Details")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=750000, step=10000)
loan_amount = st.sidebar.number_input("Loan Amount ($)", value=600000, step=10000)
interest_rate = st.sidebar.slider("Interest Rate (%)", 2.0, 10.0, 6.0, 0.1) / 100
loan_term = st.sidebar.slider("Loan Term (Years)", 10, 30, 30)
interest_only_period = st.sidebar.slider("Interest Only Period (Years)", 0, 10, 0)

st.sidebar.header("2. Income & Expenses")
weekly_rent = st.sidebar.number_input("Weekly Rent ($)", value=600, step=10)
vacancy_rate = st.sidebar.slider("Vacancy Rate (%)", 0.0, 10.0, 3.0, 0.5) / 100
annual_opex = st.sidebar.number_input("Annual Operating Expenses ($)", value=6000, help="Rates, Water, Mgmt Fees, Maintenance")
land_tax_active = st.sidebar.checkbox("Apply Land Tax?")
land_tax = st.sidebar.number_input("Annual Land Tax ($)", value=1500) if land_tax_active else 0

st.sidebar.header("3. Tax & Growth Assumptions")
marginal_tax_rate = st.sidebar.selectbox("Marginal Tax Rate", [0.0, 0.19, 0.325, 0.37, 0.45, 0.47], index=3)
capital_growth = st.sidebar.slider("Capital Growth Rate (%)", 0.0, 10.0, 5.0, 0.1) / 100
cpi_rate = st.sidebar.slider("CPI / Expense Growth (%)", 0.0, 10.0, 2.5, 0.1) / 100
holding_period = st.sidebar.slider("Planned Holding Period (Years)", 1, 30, 10)

# --- CALCULATION ENGINE ---

def calculate_scenario(p_price, l_amount, i_rate, cap_growth):
    """
    Calculates the full 30-year projection based on inputs.
    Returns a dictionary of key metrics and the dataframe.
    """
    
    # Initial Costs (Simplified for demo)
    stamp_duty = p_price * 0.04 # Est 4%
    closing_costs = 2000
    total_upfront_cost = p_price + stamp_duty + closing_costs
    initial_equity = total_upfront_cost - l_amount
    
    years = range(holding_period + 1)
    data = []

    # Running balances
    current_loan = l_amount
    current_value = p_price
    current_rent = weekly_rent * 52 * (1 - vacancy_rate)
    current_opex = annual_opex + land_tax

    cash_flows_pre_tax = [-initial_equity]
    cash_flows_post_tax = [-initial_equity]
    total_principal_paid = 0

    for year in years:
        if year == 0:
            data.append([year, p_price, l_amount, 0, 0, 0, 0, 0, 0, 0, -initial_equity])
            continue

        # 1. Inflate Income/Expenses
        current_rent *= (1 + cpi_rate) if year > 1 else 1
        current_opex *= (1 + cpi_rate) if year > 1 else 1
        
        # 2. Calculate NOI
        noi = current_rent - current_opex
        
        # 3. Loan Calcs
        if year <= interest_only_period:
            interest_payment = current_loan * i_rate
            principal_payment = 0
        else:
            # Simple PMT simulation for remaining term
            remaining_term = loan_term - (year - 1)
            if remaining_term > 0:
                payment = -npf.pmt(i_rate, remaining_term, current_loan)
                interest_payment = current_loan * i_rate
                principal_payment = payment - interest_payment
            else:
                interest_payment = 0
                principal_payment = 0 # Loan paid off
        
        # Update Loan Balance
        current_loan -= principal_payment
        if current_loan < 0: current_loan = 0
        total_principal_paid += principal_payment

        # 4. Tax Calcs (Simplified Depreciation)
        depreciation = 6000 if year <= 10 else 0 
        taxable_income = noi - interest_payment - depreciation
        tax_payable = taxable_income * marginal_tax_rate
        
        # 5. Cash Flows
        pre_tax_cf = noi - interest_payment - principal_payment
        post_tax_cf = pre_tax_cf - tax_payable
        
        # 6. Appreciation
        current_value *= (1 + cap_growth)
        
        # Store Year Data
        data.append([year, current_value, current_loan, current_rent, current_opex, noi, interest_payment, principal_payment, tax_payable, pre_tax_cf, post_tax_cf])
        
        # Add to Cash Flow Stream for IRR (excluding terminal value for now)
        if year < holding_period:
            cash_flows_pre_tax.append(pre_tax_cf)
            cash_flows_post_tax.append(post_tax_cf)

    # --- TERMINAL VALUE (SALE) ---
    sale_price = data[-1][1]
    selling_costs = sale_price * 0.025
    loan_balance = data[-1][2]
    
    # CGT Calc
    cost_base = p_price + stamp_duty + closing_costs
    gross_gain = sale_price - selling_costs - cost_base
    taxable_gain = gross_gain * 0.5 if holding_period > 1 else gross_gain # 50% Discount
    cgt_payable = taxable_gain * marginal_tax_rate
    
    net_proceeds_post_tax = sale_price - selling_costs - loan_balance - cgt_payable
    net_proceeds_pre_tax = sale_price - selling_costs - loan_balance

    # Final Year Cash Flow Adjustment for IRR
    cash_flows_post_tax.append(data[-1][10] + net_proceeds_post_tax)
    cash_flows_pre_tax.append(data[-1][9] + net_proceeds_pre_tax)

    # Metrics
    irr_post_tax = npf.irr(cash_flows_post_tax)
    irr_pre_tax = npf.irr(cash_flows_pre_tax)
    
    total_cash_in = sum(df_row[10] for df_row in data[1:]) + net_proceeds_post_tax
    total_cash_out = initial_equity + total_principal_paid
    coc_total_outlay = total_cash_in / total_cash_out if total_cash_out > 0 else 0

    df = pd.DataFrame(data, columns=["Year", "Value", "Loan", "Rent", "Opex", "NOI", "Interest", "Principal", "Tax", "Pre-Tax CF", "Post-Tax CF"])
    
    return {
        "IRR Post-Tax": irr_post_tax,
        "IRR Pre-Tax": irr_pre_tax,
        "Cash on Cash (Total)": coc_total_outlay,
        "Net Profit": sum(cash_flows_post_tax),
        "Data": df
    }

# Run Calculation for Current Inputs
results = calculate_scenario(purchase_price, loan_amount, interest_rate, capital_growth)

# --- DISPLAY OUTPUTS ---

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Internal Rate of Return (Post-Tax)", f"{results['IRR Post-Tax']:.2%}")
col2.metric("Total Cash Outlay Multiple", f"{results['Cash on Cash (Total)']:.2f}x")
col3.metric("Projected Net Profit", f"${results['Net Profit']:,.0f}")
col4.metric("Weekly Cash Flow (Year 1)", f"${results['Data'].iloc[1]['Post-Tax CF']/52:,.0f}")

# Tabs for Details vs Matrix
tab1, tab2 = st.tabs(["📈 Projections & Charts", "🎲 Sensitivity Matrix"])

with tab1:
    st.subheader(f"Year-by-Year Projections ({holding_period} Years)")
    st.dataframe(results['Data'].style.format("${:,.0f}"))
    
    st.subheader("Cash Flow vs. Equity Buildup")
    chart_data = results['Data'][['Year', 'Post-Tax CF', 'Value', 'Loan']].set_index('Year')
    chart_data['Equity'] = chart_data['Value'] - chart_data['Loan']
    st.line_chart(chart_data[['Equity', 'Post-Tax CF']])

with tab2:
    st.subheader("Sensitivity Analysis: Interest Rate vs. Capital Growth")
    st.write("See how your **Post-Tax IRR** changes under different market conditions.")
    
    # Define ranges
    growth_ranges = [0.03, 0.04, 0.05, 0.06, 0.07]
    interest_ranges = [0.04, 0.05, 0.06, 0.07, 0.08]
    
    matrix_data = []
    
    for ir in interest_ranges:
        row = []
        for cg in growth_ranges:
            # Run a mini-scenario for every combination
            res = calculate_scenario(purchase_price, loan_amount, ir, cg)
            row.append(res['IRR Post-Tax'])
        matrix_data.append(row)
        
    # Create DataFrame for Heatmap
    matrix_df = pd.DataFrame(matrix_data, 
                             index=[f"Int: {i:.0%}" for i in interest_ranges], 
                             columns=[f"Growth: {g:.0%}" for g in growth_ranges])
    
    # Display as a colored table
    st.dataframe(matrix_df.style.format("{:.2%}_{}").background_gradient(cmap="RdYlGn", axis=None))
