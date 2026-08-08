# 🚀 Sovereign Engine: Launch TODO List

This list tracks the final steps to "stock the store" and activate your financial pipelines ($+\$$).

---

## 🟢 Phase 1: Environment & Credentials
- [ ] **Create `.env` File**: Copy `.env.example` to `.env` in `C:\Users\Jinx\projects\jinxmp3-site\`.
- [ ] **Input Shopify Token**: Add your `SHOPIFY_ADMIN_TOKEN` and `SHOPIFY_STORE_DOMAIN`.
- [ ] **Input Stripe Keys**: Add `STRIPE_SECRET_KEY` and `STRIPE_PUBLIC_KEY` to the `.env` file (since the API is already on your computer).
- [ ] **Verify Paths**: Ensure `JINX_MUSIC_DIR` points to your Suno/DistroKid vault.

---

## 📦 Phase 2: Stocking the Store (Shopify)
- [ ] **Run Initial Catalog Scan**: 
  ```bash
  python scripts/jinxmp3_master.py --task catalog
  ```
- [ ] **Sync to Shopify**: This "stocks" your store by creating products for all 447 releases.
  ```bash
  python scripts/shopify_store_agent.py --sync
  ```
- [ ] **Verify Shopify Admin**: Log in to `jinxmp3.myshopify.com` and confirm products are "Active" and have the correct cover art.

---

## 💳 Phase 3: Financial Integration (Stripe)
- [ ] **Link Local Stripe API**: Since the Stripe API is already on your computer, ensure the `jinxmp3_master.py` or a new `stripe_agent.py` can call it.
- [ ] **Configure Webhooks**: Set up Stripe webhooks to trigger a "Thank You" email or download link delivery when a payment succeeds.
- [ ] **Test Transaction**: Run a \$1.00 test purchase to verify the pipeline from `index.html` → Stripe → Success.

---

## 🌐 Phase 4: Infrastructure & Launch
- [ ] **Cloudflare Tunnel Ignition**:
  ```bash
  python scripts/jinxmp3_master.py --task tunnel
  ```
- [ ] **DNS Verification**: Confirm `www.jinxmp3.com` resolves to your local Node server.
- [ ] **Activate Agent Loop**: Start the background agent to monitor health and auto-commit changes.
  ```bash
  python scripts/jinxmp3_master.py --task agent
  ```

---

## 📈 Success Metric ($+\$$)
- [ ] **First Sale**: Verify a net-positive yield from a digital download.
- [ ] **Zero Churn**: System handles a tunnel failure or server crash without human intervention.

> **Next Action:** Open your `.env` file and fill in the Shopify and Stripe keys to begin **Phase 2**.
