# How to get Instagram API access (for the photographer's own account)

Takes about 30–60 minutes. Your friend does these steps himself, on a laptop, logged in as himself.
Meta renames menus from time to time; if a label differs slightly, look for the closest match.

## Step 1: Switch Instagram to a Professional account (phone, 2 min)
1. Instagram app → Profile → ☰ menu → **Settings and privacy**.
2. **Account type and tools** → **Switch to professional account**.
3. Choose **Creator** or **Business**; pick category **Photographer** (or Videographer).
4. Keep the account **public**.
5. Turn on two-factor authentication (Settings → Accounts Center → Password and security).

## Step 2: Create a Meta Developer account (5 min)
1. Go to **developers.facebook.com** → **Get Started**, log in with Facebook
   (create a personal Facebook account if he has none).
2. Verify phone number/email and accept the developer terms.

## Step 3: Create the app (5 min)
1. **My Apps** → **Create App**.
2. App name: e.g. `PhotoGrowthAgent` (avoid the word "Instagram" in the name).
3. Use case: **Manage messaging & content on Instagram**.
4. Business portfolio: skip for now, or connect his business if he has one.
5. Finish. The app opens in **Development** mode, which is fine for his own account.

## Step 4: Set up "API setup with Instagram business login" (10 min)
1. In the app dashboard: **Use cases** → **Customize** (Instagram) → **API setup with Instagram business login**.
   Do not pick the "Facebook Login" variant; this version needs no Facebook Page.
2. Note down the **Instagram App ID** and **Instagram App Secret** shown on this page.
   (These are different from the main Meta App ID.)
3. Under permissions, make sure these are added:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
   - `instagram_business_manage_comments`
   - `instagram_business_manage_messages`
   - `instagram_business_manage_insights` (if listed separately)

## Step 5: Connect his Instagram account and generate the token (5 min)
1. Same page → **Generate access tokens** → **Add account**.
2. A popup opens; log in with **his Instagram account** and allow all permissions.
   (If it asks to accept a tester invite: Instagram app → Settings → Website permissions /
   Apps and websites → **Tester invites** → Accept, then retry.)
3. Click **Generate token** next to his account and **copy the token immediately**. It is
   long-lived (valid 60 days); the agent refreshes it automatically before it expires.
4. Note the **Instagram User ID** shown next to the account.

## Step 6: Quick test (2 min)
Paste this in a browser (replace TOKEN):
```
https://graph.instagram.com/me?fields=user_id,username,followers_count,media_count&access_token=TOKEN
```
If it shows his username and follower count, it works.

## Step 7: Get the Claude API key (5 min)
1. **console.anthropic.com** → sign up → add billing.
2. **Settings → Limits**: set a monthly spend limit (e.g. $50).
3. **API Keys** → **Create Key** → copy it (shown only once).

## Step 8: Send the credentials safely
Send these 5 items through a password manager share (Bitwarden Send / 1Password), never in WhatsApp,
email or a GitHub file:

| Item | Where it came from |
|---|---|
| Instagram App ID | Step 4 |
| Instagram App Secret | Step 4 |
| Instagram User ID | Step 5 |
| Long-lived access token | Step 5 |
| Anthropic API key | Step 7 |

**Never share his Instagram password.** None of the above needs it.

## Later, during the build (not needed now)
- **Webhooks** (real-time comments and DMs) are configured once the server URL exists.
- If customer comments/DMs don't arrive while the app is in Development mode, we'll switch it to
  **Live** (needs a privacy policy URL; we'll create a simple page).
- App Review / Business Verification is only needed if this ever serves other photographers' accounts.
