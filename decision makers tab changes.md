# **For Decision Makers** 

# **Decision Maker Enrichment — Build Spec** 

## **What's changing** 

Right now the system only searches FullEnrich for talent-acquisition titles and returns 1 person with 1 email per company. We want up to 3 decision makers per company, chosen by a priority list that depends on company size, each with a usable email. 

## **Step 1: Pick the title list based on company headcount** 

**If headcount is 50–200** → use List A (in this order): 

1. Head of Talent Acquisition / Head of Recruiting 

2. Director of Talent Acquisition / Recruiting Manager 

3. Head of People / VP of People 

4. HR Director / Head of HR 

5. Talent Acquisition Manager / Talent Partner / Talent Lead 

6. Founder / Co-founder 

### 7. CEO 

8. VP of Engineering / Head of Engineering (or the function head for whatever role is open) 

9. COO 

10. Chief Executive Officer 

**If headcount is 200+** → use List B (in this order): 

1. VP of Talent Acquisition 

2. Head of Talent Acquisition / Head of Recruiting 

3. Director of Talent Acquisition / Director of Recruiting 

4. Chief People Officer / Chief Human Resources Officer 

5. VP of People / VP of HR 

6. Talent Acquisition Manager / Recruiting Manager 

7. HR Director 

8. VP of Engineering / Director of Engineering (or the function head owning the open role) 

The order matters. Titles near the top are the ones we most want. 

## **Step 2: Find up to 3 people** 

### **Goal: 3 people per company. Work down the list from the top until you have them.** 

How it works: 

1. Take the first few titles from the list and search FullEnrich People Search for them, filtered to that company. 

2. Count how many people came back. 

3. If you have 3, stop. 

4. If you got fewer than 3 (say only 2 came back), go to the next titles down the list and search again to fill the gap. 

5. Repeat until you have 3 people, or until you've worked through the whole list. 

If the list runs out and you only found 1 or 2 people, that's fine. Move on with what you have. 

Note on the API: current_position_titles treats multiple titles as OR, so a search with several titles returns anyone matching any of them, with no ranking. That's why we work down the list in order and stop early, instead of throwing all 10 titles into one search. 

## **Step 3: Get emails for those people** 

FullEnrich returns one of four email statuses: 

- DELIVERABLE — 2% bounce rate. Best. 

- HIGH_PROBABILITY — 9% bounce rate, catch-all but likely valid. Acceptable. 

- CATCH_ALL — higher bounce rate. Not acceptable, doesn't count. 

- INVALID — will bounce. Not acceptable, doesn't count. 

**What we want:** an acceptable email for each of the 3 people, and at least 1 of them must be 

#### DELIVERABLE . 

Good outcomes: 

- 2 DELIVERABLE + 1 HIGH_PROBABILITY ✅ 

- 1 DELIVERABLE + 2 HIGH_PROBABILITY ✅ 

- 3 DELIVERABLE ✅ 

Not good enough on its own: 

3 HIGH_PROBABILITY with zero DELIVERABLE ❌ (keep trying) 

How it works: 

1. Search emails for the 3 people found in Step 2, one at a time. 

2. Check what you have against the target above. 

3. If the target is met, you're done. Ship the record. 

4. If not, go back to the title list, pull the next person down the priority order (the 4th, then 5th, and so on), search their email, and check again. 

5. Keep going until the target is met or you run out of titles. 

**Only fetch one more person when you actually need one.** Don't pre-fetch 5 or 6 people upfront — every extra lookup costs FullEnrich credits, and most companies will hit the target on the first 3. 

## **When it doesn't work out** 

If you've gone through the whole title list and still haven't hit the target — say you end up with only 1 DELIVERABLE and nothing else usable — **ship the record as-is with whatever emails you got.** No manual review flag, no blocking. Fewer than 3 emails is acceptable. Same goes for Step 2: if a company only has 1 or 2 findable people, ship it with 1 or 2. 

