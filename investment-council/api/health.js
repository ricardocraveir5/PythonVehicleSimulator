module.exports = function handler(req, res) {
  res.status(200).json({
    status: "ok",
    hasAnthropicKey: !!process.env.ANTHROPIC_API_KEY,
    hasFinancialKey: !!process.env.FINANCIAL_DATASETS_API_KEY,
  });
};
