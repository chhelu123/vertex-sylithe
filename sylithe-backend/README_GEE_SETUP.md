# Google Earth Engine (GEE) Analytics Setup

To enable real satellite analytics (histograms and boxplots) on the Developer Dashboard, you must provide your Google Earth Engine API credentials to the backend.

1. Open your backend environment file: `/Users/karan/Desktop/sylithe/backend/.env`
2. Add your Service Account JSON or Project ID configuration.

```env
# Option 1: Provide the absolute path to your downloaded Service Account JSON key (Recommended)
GEE_SERVICE_ACCOUNT_PATH=/path/to/your-service-account-key.json

# Option 2: Use standard Google Cloud credentials
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

If these are not provided, the `/api/gee/analytics` route will return fallback **mock distributions** so the frontend UI can still render Recharts histograms and box plots perfectly.
