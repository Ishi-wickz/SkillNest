**Student:** W.M.I.P. Wickramasinghe (24IT0545)
**Course project:** SkillNest, a freelancing marketplace

# SkillNest

A freelancing marketplace where clients post jobs and freelancers send proposals,
chat with clients, and build a reputation through reviews.

Built with Django, Django REST Framework, Django Channels (WebSockets), PostgreSQL,
and vanilla HTML, CSS and JavaScript.

## Features

**Accounts and security**
- Sign up as a Client or a Freelancer, with login and logout
- Session login with CSRF protection and rate-limited login
- Email verification and password reset (signed, expiring, single-use links)
- Role-based permissions, with ownership checks on every action
- Django admin for moderating users, jobs, proposals, reviews and chats

**Jobs and proposals**
- Clients post jobs (category, fixed or hourly budget, USD or LKR, skills) and can cancel open ones
- Public job feed with keyword, category and budget filters, and pagination
- Freelancers send one proposal per job and can withdraw it while it is pending
- Clients accept or reject proposals (accepting is one transaction that rejects the rest)
- Dashboards for both roles, with pagination

**Completion and reviews**
- Clients mark jobs complete and leave a 1 to 5 star review
- Ratings show on talent cards and public profiles

**Talent**
- Profile editing (bio for everyone, hourly rate and skills for freelancers)
- Find Talent with keyword, skill and rate filters
- Public freelancer profile pages

**Messaging and notifications**
- Real-time chat between a client and a freelancer, tied to a job and a proposal
- Polling fallback when WebSockets are unavailable
- Notification bell with a live badge, pop-ups and a notifications page
- Email notifications for verified users, which can be switched off

## Tech and design decisions
- **REST is the source of truth.** WebSockets only signal that something changed, and the browser fetches the data over REST, so no message is lost if a connection drops.
- **Rules live in a services layer** (`services.py`), not in views, so they are testable.
- **The database enforces key rules** with constraints: one proposal per job per freelancer, one accepted proposal per job, ratings between 1 and 5, positive amounts.
- **Concurrency:** accepting, withdrawing and submitting proposals lock the job row, so two simultaneous clicks cannot both succeed.
- **Privacy:** public API responses never include email addresses. Other users' items return 404, not 403.
- **XSS:** user text is rendered with `textContent`, never `innerHTML`.
- **Email links** use `SITE_URL` from settings, never the request's Host header.

## Run locally
1. Install Python 3.12+, PostgreSQL and Git.
2. Create a PostgreSQL user and database named `skillnest`.
3. In `backend/`:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Create `backend/.env`:
   ```
   DJANGO_SECRET_KEY=your-long-random-key
   DJANGO_DEBUG=True
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   DATABASE_URL=postgres://skillnest:YOUR_PASSWORD@localhost:5432/skillnest
   ```
5. Set up and start:
   ```
   python manage.py migrate
   python manage.py seed
   python manage.py createsuperuser
   python manage.py runserver
   ```
6. Open http://127.0.0.1:8000/

Emails print in the `runserver` terminal. For real delivery, add `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL` to `.env`.

## Tests
```
python manage.py test
```

## Project layout
```
backend/
  config/               settings, URLs, ASGI
  apps/accounts/        users, profiles, auth, email flows, talent API
  apps/marketplace/     categories, skills, jobs, proposals, reviews
  apps/chat/            conversations, messages, WebSocket consumer
  apps/notifications/   notifications, email alerts, WebSocket consumer
  static/               CSS and JavaScript
  templates/            HTML pages
```

## Limitations and next steps
This project was built to a fixed scope. These are not included:

- **Hosting:** it runs locally only. Links in emails point to `127.0.0.1` unless `SITE_URL` is set.
- **Payments:** no escrow, invoices, platform fees, payouts or time tracking. An accepted proposal plus the job status acts as the contract.
- **Uploads:** no profile photos, portfolios or job attachments (this needs file storage such as S3).
- **Disputes and moderation:** handled by hand in the admin. There is no reporting or blocking.
- **Accounts:** no change of password or email while logged in, no social login, no two-factor authentication.
- **Reviews** go one way, from client to freelancer.
- **Marketplace extras:** no saved jobs, invitations, job editing after posting, or recommendations.
- **Chat:** no attachments, typing indicators, or message editing.
- **Scaling:** the in-memory WebSocket layer and email limits suit one server process. Several processes need Redis.
- **Operations:** no error tracking, backups or analytics.

## Quick demo
1. Run the app (see "Run locally").
2. Sign up as a Client in a normal window, and as a Freelancer in an incognito window.
3. Client posts a job, the freelancer sends a proposal, the client accepts it.
4. Chat, mark the job complete, then leave a review.
Emails print in the terminal, so verification links appear there.