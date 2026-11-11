# Denver Violins dashboards

- **`report/`**: the new report, a read-only view of the `rpt_*` tabs in the dv_clean sheet. See `report/README.md`.
- **`dashboard/`**: the original dashboard, kept running until the new pipeline is cut over.

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run dashboard/app.py
   ```
