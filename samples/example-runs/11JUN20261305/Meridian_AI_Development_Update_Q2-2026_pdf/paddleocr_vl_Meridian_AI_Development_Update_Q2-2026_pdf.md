

# Q2 2026 AI Development & Adoption Update

Quarterly memorandum from the AI Platform Group

TO: Executive Leadership Council; Business Unit General Managers

FROM: Dr. Elena Marchetti, VP of AI Platforms & Research

DATE: 11 June 2026

RE: Second-quarter development progress, adoption maturity, and 2H roadmap

The second quarter marked the transition of the Meridian AI Platform from a single-region deployment to an actively replicated, multi-region service with a contractual 99.9% availability target. Platform request volume grew 38% quarter over quarter, driven primarily by the general availability of Atlas engineering copilots across all product lines and the first production cohorts of Foundry agentic workflows in Procurement. We completed the migration of all retrieval workloads to the consolidated vector store, retiring three legacy pilot systems and reducing per-query infrastructure cost by 27%. Model evaluation coverage — the share of production traffic flowing through automated quality and safety evaluation — reached 96%, up from 81% at the end of Q1.

Adoption maturity, however, remains uneven across the enterprise, and closing that gap is the central theme of our second-half plan. The heatmap below summarizes the quarterly maturity assessment conducted with each department, scoring five capability areas on a five-point scale that weighs usage breadth, workflow integration depth, measured outcomes, and local governance practice. Engineering and Customer Support continue to lead, reflecting two full years of investment. Legal & Compliance scores low on automation by deliberate design — their workload emphasizes retrieval and drafting assistance — but Human Resources represents a genuine adoption of shortfall that we are addressing with a dedicated enablement sprint in July.

<div style="text-align: center;">AI Capability Maturity Heatmap — Q2 2026 Assessment</div>


<table border=1 style='margin: auto; width: max-content;'>
  <thead><tr><th style='text-align: center;'></th><th style='text-align: center;'>Generative Drafting</th><th style='text-align: center;'>Predictive Analytics</th><th style='text-align: center;'>Process Automation</th><th style='text-align: center;'>Knowledge Retrieval</th><th style='text-align: center;'>Decision Support</th></tr></thead>
  <tbody>
    <tr><td style='text-align: center;'>Engineering</td><td style='text-align: center;'>4.6</td><td style='text-align: center;'>4.2</td><td style='text-align: center;'>4.4</td><td style='text-align: center;'>4.8</td><td style='text-align: center;'>3.9</td></tr>
    <tr><td style='text-align: center;'>Operations</td><td style='text-align: center;'>3.1</td><td style='text-align: center;'>4.5</td><td style='text-align: center;'>4.7</td><td style='text-align: center;'>3.4</td><td style='text-align: center;'>4.0</td></tr>
    <tr><td style='text-align: center;'>Finance</td><td style='text-align: center;'>3.8</td><td style='text-align: center;'>4.3</td><td style='text-align: center;'>3.9</td><td style='text-align: center;'>3.2</td><td style='text-align: center;'>4.1</td></tr>
    <tr><td style='text-align: center;'>HR</td><td style='text-align: center;'>3.5</td><td style='text-align: center;'>2.6</td><td style='text-align: center;'>3.0</td><td style='text-align: center;'>3.8</td><td style='text-align: center;'>2.4</td></tr>
    <tr><td style='text-align: center;'>Sales & Marketing</td><td style='text-align: center;'>4.4</td><td style='text-align: center;'>3.7</td><td style='text-align: center;'>2.9</td><td style='text-align: center;'>4.1</td><td style='text-align: center;'>3.3</td></tr>
    <tr><td style='text-align: center;'>Customer Support</td><td style='text-align: center;'>4.7</td><td style='text-align: center;'>3.2</td><td style='text-align: center;'>4.1</td><td style='text-align: center;'>4.6</td><td style='text-align: center;'>3.6</td></tr>
    <tr><td style='text-align: center;'>Legal & Compliance</td><td style='text-align: center;'>2.8</td><td style='text-align: center;'>2.2</td><td style='text-align: center;'>2.5</td><td style='text-align: center;'>3.9</td><td style='text-align: center;'>2.7</td></tr>
  </tbody>
</table>

<div style="text-align: center;">Figure 1. Departmental AI capability maturity, Q2 2026 self-assessment validated by the AI Platform Group. Scale: 1 (exploratory) to 5 (optimized and governed).</div>


## Platform Workload Growth

Workload mix is shifting in line with the strategy. Engineering copilots remain the largest single consumer of platform capacity, but agentic workflows are the fastest-growing category, expanding from roughly ten thousand requests in January to two hundred forty thousand in May as Procurement's vendor-onboarding agents entered production. Retrieval-augmented knowledge workloads grew steadily as the consolidated policy corpus expanded to 1.9 million documents. Capacity planning for the second half assumes a further 2.5x increase in agentic traffic, which is the primary driver of the incremental inference budget submitted to Finance in May.

<div style="text-align: center;">Internal AI Platform Usage by Workload, 2026 YTD</div>


<table border=1 style='margin: auto; width: max-content;'>
  <thead><tr><th style='text-align: center;'></th><th style='text-align: center;'>Jan</th><th style='text-align: center;'>Feb</th><th style='text-align: center;'>Mar</th><th style='text-align: center;'>Apr</th><th style='text-align: center;'>May</th></tr></thead>
  <tbody>
    <tr><td style='text-align: center;'>Engineering copilots</td><td style='text-align: center;'>180</td><td style='text-align: center;'>220</td><td style='text-align: center;'>300</td><td style='text-align: center;'>400</td><td style='text-align: center;'>470</td></tr>
    <tr><td style='text-align: center;'>Knowledge retrieval (RAG)</td><td style='text-align: center;'>80</td><td style='text-align: center;'>120</td><td style='text-align: center;'>180</td><td style='text-align: center;'>250</td><td style='text-align: center;'>320</td></tr>
    <tr><td style='text-align: center;'>Agentic workflows</td><td style='text-align: center;'>20</td><td style='text-align: center;'>30</td><td style='text-align: center;'>50</td><td style='text-align: center;'>100</td><td style='text-align: center;'>180</td></tr>
  </tbody>
</table>

<div style="text-align: center;">Figure 2. Monthly platform requests by workload category, January–May 2026 (thousands). Source: platform gateway telemetry.</div>


<div style="text-align: center;">Delivery Highlights & Operational Metrics</div>



<table border=1 style='margin: auto; word-wrap: break-word;'><tr><td style='text-align: center; word-wrap: break-word;'>Metric</td><td style='text-align: center; word-wrap: break-word;'>Q1 2026</td><td style='text-align: center; word-wrap: break-word;'>Q2 2026</td><td style='text-align: center; word-wrap: break-word;'>$ \Delta $ QoQ</td><td style='text-align: center; word-wrap: break-word;'>2H Target</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>Production AI services in catalog</td><td style='text-align: center; word-wrap: break-word;'>31</td><td style='text-align: center; word-wrap: break-word;'>42</td><td style='text-align: center; word-wrap: break-word;'>+35%</td><td style='text-align: center; word-wrap: break-word;'>55</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>Monthly active platform users</td><td style='text-align: center; word-wrap: break-word;'>3,120</td><td style='text-align: center; word-wrap: break-word;'>4,610</td><td style='text-align: center; word-wrap: break-word;'>+48%</td><td style='text-align: center; word-wrap: break-word;'>6,000</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>Median gateway latency (p50, ms)</td><td style='text-align: center; word-wrap: break-word;'>640</td><td style='text-align: center; word-wrap: break-word;'>410</td><td style='text-align: center; word-wrap: break-word;'>-36%</td><td style='text-align: center; word-wrap: break-word;'>≤400</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>Eval coverage of production traffic</td><td style='text-align: center; word-wrap: break-word;'>81%</td><td style='text-align: center; word-wrap: break-word;'>96%</td><td style='text-align: center; word-wrap: break-word;'>+15 pts</td><td style='text-align: center; word-wrap: break-word;'>≥98%</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>Safety incidents (Sev-2 or higher)</td><td style='text-align: center; word-wrap: break-word;'>3</td><td style='text-align: center; word-wrap: break-word;'>1</td><td style='text-align: center; word-wrap: break-word;'>-2</td><td style='text-align: center; word-wrap: break-word;'>0</td></tr><tr><td style='text-align: center; word-wrap: break-word;'>Mean cost per 1K requests</td><td style='text-align: center; word-wrap: break-word;'>2.31</td><td style='text-align: center; word-wrap: break-word;'>1.68</td><td style='text-align: center; word-wrap: break-word;'>-27%</td><td style='text-align: center; word-wrap: break-word;'>1.40</td></tr></table>

<div style="text-align: center;">Table 1. AI Platform operational scorecard. Targets ratified by the CTO staff on 28 May 2026.</div>


## Risks and Second-Half Priorities

Three risks dominate our register. First, agentic autonomy governance: the Responsible AI Council's autonomy framework must be ratified before Foundry scales beyond Procurement; absent that, we will hold new agentic launches even at the cost of roadmap slippage. Second, evaluation debt: while coverage is high, several older services rely on first-generation test suites that predate our current rubric, and a remediation sprint is scheduled for August. Third, concentration risk in our primary model vendor; the gateway's multi-provider abstraction is complete, and we will qualify a second frontier-model provider for Tier-1 workloads by October. Our second-half priorities are, in order: ratify and operationalize the autonomy framework, close the HR adoption gap, qualify the second model provider, and deliver the unified evaluation dashboard to business-unit leaders so that adoption maturity becomes a self-service metric rather than a quarterly survey.