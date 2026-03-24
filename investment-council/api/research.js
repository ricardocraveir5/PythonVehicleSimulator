const Anthropic = require("@anthropic-ai/sdk");

const BASE_URL = "https://api.financialdatasets.ai";

async function callApi(endpoint, params, apiKey) {
  const url = new URL(endpoint, BASE_URL);
  for (const [k, v] of Object.entries(params)) { if (v != null) url.searchParams.set(k, v); }
  const res = await fetch(url.toString(), { headers: { "X-API-KEY": apiKey } });
  if (!res.ok) return { error: `API ${res.status}` };
  return res.json();
}

async function analyzeCompany(ticker, apiKey) {
  const [inc, bal, cf] = await Promise.all([
    callApi("/financials/income-statements/", { ticker, period: "annual", limit: 5 }, apiKey),
    callApi("/financials/balance-sheets/", { ticker, period: "annual", limit: 5 }, apiKey),
    callApi("/financials/cash-flow-statements/", { ticker, period: "annual", limit: 5 }, apiKey),
  ]);
  const fmt = v => `$${(v / 1e9).toFixed(2)}B`;
  const statements = inc.income_statements || [];
  const sheets = bal.balance_sheets || [];
  const flows = cf.cash_flow_statements || [];
  let s = `=== ${ticker.toUpperCase()} Financial Summary ===\n\nKEY METRICS:\n`;
  if (statements.length > 0) {
    const l = statements[0];
    if (l.revenue) s += `  Revenue: ${fmt(l.revenue)}\n`;
    if (l.gross_profit && l.revenue) s += `  Gross Margin: ${(l.gross_profit/l.revenue*100).toFixed(1)}%\n`;
    if (l.operating_income && l.revenue) s += `  Operating Margin: ${(l.operating_income/l.revenue*100).toFixed(1)}%\n`;
    if (l.net_income && l.revenue) s += `  Net Margin: ${(l.net_income/l.revenue*100).toFixed(1)}%\n`;
    if (l.net_income) s += `  Net Income: ${fmt(l.net_income)}\n`;
    if (statements.length >= 2 && statements[1].revenue) s += `  Revenue Growth YoY: ${((l.revenue-statements[1].revenue)/statements[1].revenue*100).toFixed(1)}%\n`;
  }
  if (sheets.length > 0) {
    const l = sheets[0];
    if (l.total_debt && l.shareholders_equity) s += `  Debt/Equity: ${(l.total_debt/l.shareholders_equity).toFixed(2)}\n`;
    if (l.current_assets && l.current_liabilities) s += `  Current Ratio: ${(l.current_assets/l.current_liabilities).toFixed(2)}\n`;
    if (statements.length > 0 && statements[0].net_income && l.shareholders_equity) s += `  ROE: ${(statements[0].net_income/l.shareholders_equity*100).toFixed(1)}%\n`;
  }
  if (flows.length > 0) {
    const l = flows[0];
    if (l.free_cash_flow) s += `  Free Cash Flow: ${fmt(l.free_cash_flow)}\n`;
    if (l.free_cash_flow && statements.length > 0 && statements[0].revenue) s += `  FCF Margin: ${(l.free_cash_flow/statements[0].revenue*100).toFixed(1)}%\n`;
  }
  if (statements.length > 1) {
    s += "\nREVENUE TREND:\n";
    statements.slice(0,5).forEach(i => { s += `  ${i.report_period}: ${i.revenue ? fmt(i.revenue) : "N/A"}\n`; });
  }
  if (flows.length > 1) {
    s += "\nFCF TREND:\n";
    flows.slice(0,5).forEach(i => { s += `  ${i.report_period}: ${i.free_cash_flow ? fmt(i.free_cash_flow) : "N/A"}\n`; });
  }
  return s;
}

const ADVISORS = {
  analyst: { name: "Systematic Analyst", icon: "📊", system: "You are an elite systematic investment analyst. Synthesize data across macro, sectors, valuation, technicals, risk, and fundamentals. Reference specific tickers and metrics. Always surface risks. Keep responses 200-350 words." },
  buffett: { name: "Warren Buffett", icon: "🎩", system: "You think like Warren Buffett. Focus on moats, owner earnings, margin of safety, long-term compounding. Folksy Omaha wisdom, baseball metaphors. Reference Berkshire holdings. Optimistic about America. Keep responses 200-350 words." },
  munger: { name: "Charlie Munger", icon: "📚", system: "You think like Charlie Munger. Apply mental models (incentives, inversion, opportunity cost, lollapalooza effects). Be blunt and acerbic. Quote Jacobi, reference Costco/BYD. Despise crypto and complexity. Keep responses 200-350 words." },
};

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const { question, ticker, advisors = ["analyst","buffett","munger"] } = req.body || {};
  if (!question) return res.status(400).json({ error: "No question" });

  let ctx = "";
  if (ticker && process.env.FINANCIAL_DATASETS_API_KEY) {
    try { ctx = await analyzeCompany(ticker, process.env.FINANCIAL_DATASETS_API_KEY); }
    catch (e) { ctx = `(Could not retrieve data for ${ticker}: ${e.message})`; }
  }

  if (!process.env.ANTHROPIC_API_KEY) return res.status(500).json({ error: "ANTHROPIC_API_KEY not configured" });
  const anthropic = new Anthropic.default({ apiKey: process.env.ANTHROPIC_API_KEY });
  const q = ctx ? `${ctx}\n\n---\nBased on this data:\n${question}` : question;
  const results = {};

  for (const key of advisors) {
    if (!ADVISORS[key]) continue;
    try {
      const response = await anthropic.messages.create({ model: "claude-sonnet-4-20250514", max_tokens: 1200, system: ADVISORS[key].system, messages: [{ role: "user", content: q }] });
      const text = response.content.filter(b => b.type === "text").map(b => b.text).join("\n");
      results[key] = { ok: true, text, name: ADVISORS[key].name, icon: ADVISORS[key].icon };
    } catch (err) {
      results[key] = { ok: false, text: `Error: ${err.message}`, name: ADVISORS[key].name, icon: ADVISORS[key].icon };
    }
  }
  res.status(200).json({ results, financialContext: ctx || null });
};
