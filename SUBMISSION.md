# Submission text (copy into the hackathon form)

**Project name:** Arhata (అర్హత) — the scholarships you can claim

**Problem statement:** PS5 · Citizens and Public Services · Claim What's Yours

**One-line description:**
A student in Telangana describes their life in plain words (typed or spoken, in Telugu, Hindi or English) and Arhata shows which scholarships they are likely eligible for, the exact rule behind each match, the documents to collect, the steps on the official portal, and reminders before every last date.

**Description (about 150 words):**
Every year, eligible students in Telangana miss scholarships because the rules are scattered and hard to read, the document list is unclear, and middlemen charge for help that should be free. Arhata asks for nothing but plain words, never an ID number. It reads the message (offline, or with Claude when a key is set) and asks only the few questions that would change a result. A plain rules engine then checks 10 Telangana and central schemes: ePASS, fee reimbursement, NMMS, Central Sector, AICTE Pragati and Saksham, and PM-Vidyalaxmi. Every match shows its rule and the student's own answer. The result is a personal checklist, portal steps, and a tracker with reminders, all in Telugu, Hindi or English. Rules are stored as editable data with a last-verified date. It is free for students; CSR funds, NGOs and Mee Seva centres pay through Helper mode, which includes printable checklists.

**Team:** (fill in your names / solo)

**GitHub repository:** https://github.com/vedangikarthik/hakku-claim-whats-yours

**How to run:** see README.md (`pip install -r requirements.txt`, then `python app.py`, open http://127.0.0.1:5050).

**Demo path for judges (2 minutes):**
1. Home → tap "Ravi" → results with the reasons.
2. Open "AICTE Pragati" → not a match, with the one rule that failed.
3. New search in Telugu: "నేను డిగ్రీ మొదటి సంవత్సరం, మా ఊరు నల్గొండ, మేము SC, మా ఆదాయం 80 వేలు" → one quick question → results.
4. Add a scheme to My tracker → tick documents → see the next step.
5. Switch to తెలుగు or हिंदी in the top bar.
6. /helper (operator mode, print checklist) and /about (who pays).
