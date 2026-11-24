const assert = require('node:assert/strict');
const format = require('../web/journal-title.js');
const examples = new Map([
  ['EUROPEAN JOURNAL OF MARKETING', 'European Journal of Marketing'],
  ['JOURNAL OF CONSUMER RESEARCH', 'Journal of Consumer Research'],
  ['Academy of Management Perspectives', 'Academy of Management Perspectives'],
  ['ACM Transactions on Economics and Computation', 'ACM Transactions on Economics and Computation'],
  ['IEEE TRANSACTIONS ON AUTOMATIC CONTROL', 'IEEE Transactions on Automatic Control'],
  ['BMC PUBLIC HEALTH', 'BMC Public Health'],
  ['JAMA NETWORK OPEN', 'JAMA Network Open'],
  ['PLOS ONE', 'PLOS One'],
  ['eLife', 'eLife'], ['mBio', 'mBio'], ['iScience', 'iScience'],
  ['CA-A CANCER JOURNAL FOR CLINICIANS', 'CA-A Cancer Journal for Clinicians'],
  ['ACCOUNTING & FINANCE', 'Accounting & Finance'],
  ['BIOLOGY: METHODS AND PROTOCOLS', 'Biology: Methods and Protocols'],
  ['Children\'s Geographies', 'Children\'s Geographies'],
  ['Revue de l\'Histoire des Religions', 'Revue de l\'Histoire des Religions'],
  ['A JOURNAL OF THIS OR THAT', 'A Journal of This or That'],
  ['OR Spectrum', 'OR Spectrum'], ['Journal of the OR Society', 'Journal of the OR Society'],
  ['EuROPEAN JOURNAL OF MARKETING', 'European Journal of Marketing'],
  ['J.A.M.A. Archives', 'J.A.M.A. Archives'],
  ['BioMed Research International', 'BioMed Research International'],
  ['国际新闻界', '国际新闻界'], ['', '']
]);
for (const [input, expected] of examples) {
  assert.equal(format(input), expected, input);
  assert.equal(format(expected), expected, `Stable display: ${expected}`);
}
console.log(`${examples.size} title display cases passed`);
