/* Display casing only. Source titles and journal identifiers remain untouched. */
(() => {
  'use strict';
  const minor = new Set('a an and as at but by for from in into nor of on or per the to via vs with de del der des di du el en et la le les und van von'.split(' '));
  const acronyms = new Set(('AAAS AAPS AATCC ACM ACI ACS AIAA AIP AIMS AIS AMA AMIA AMS ANZ APA APS ASA ASCE ASH ASME ASM ASP AWWA BMC BMJ BSE CA CAD CAM CBE CNS DNA EAI EEG EMBO EMJ ERP ESA ESC EURASIP FEBS FEMS FASEB G3 GSA HEC HIV HLA HNO IAENG IAHS IAS IAU IBS ICES ICT IEEE IEICE IET IMA IMF IMS INFORMS IOP IOS IP IRE ISA ISIJ ISPRS ISSN IT IUBMB IUCr JACC JACS JAMA JASA JBC JCI JCO JCR JHEP JMLR JMIR JMR JNCI JOSA JOT KDI KIE KONA LSE MRS MSOR NASA NATO NEJM NMR OECD OIE OR ORL ORYX PNAS PLOS PRL PRX QJM QJE RAE RAI RAN RCT RNA RSC RSF RSS SAE SAH SAGE SAMJ SAR SEM SIAM SIGMOD SIGPLAN SIGIR SIGKDD SIGGRAPH SIS SOHO SPIE STEM TQM TV UCL UCLA UK UN UNESCO US USA USDA USGS UV VDI WASET WHO WIREs WSEAS ZDM ZEFQ').split(' '));
  const brands = new Map([
    ['elife', 'eLife'], ['eneuro', 'eNeuro'], ['iscience', 'iScience'], ['mbio', 'mBio'],
    ['mhealth', 'mHealth'], ['mpath', 'mPath'], ['npj', 'npj'], ['iosr', 'IOSR'],
    ['iucr', 'IUCr'], ['wires', 'WIREs'], ['plos', 'PLOS'], ['arxiv', 'arXiv'], ['asta', 'AStA']
  ]);
  const format = value => {
    const text = String(value ?? '').trim();
    const words = [...text.matchAll(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu)];
    let position = 0;
    return text.replace(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu, (word, offset) => {
      const index = position++, lower = word.toLowerCase(), upper = word.toUpperCase();
      const startsPart = index === 0 || /[:—–]\s*$/.test(text.slice(0, offset));
      if (word.length === 1 && (text[offset - 1] === '.' || text[offset + 1] === '.')) return upper;
      if (minor.has(lower) && !startsPart && index !== words.length - 1 && !(word === 'OR' && /\p{Ll}/u.test(text))) return lower;
      if (brands.has(lower)) return brands.get(lower);
      if (acronyms.has(upper)) return upper === 'IUCR' ? 'IUCr' : upper === 'WIRES' ? 'WIREs' : upper;
      if (/^[dlo]['’]\p{L}/iu.test(word)) {
        const prefix = lower[0] === 'o' || startsPart ? upper[0] : lower[0];
        return prefix + word[1] + lower.slice(2).replace(/^\p{L}/u, letter => letter.toUpperCase());
      }
      // Retain source-supplied internal capitals, including scientific brands.
      if (/^(?:\p{Ll}+|\p{Lu}\p{Ll}+)\p{Lu}\p{Ll}+(?:\p{Lu}\p{Ll}+)*$/u.test(word)) return word;
      if (/^(?:II|III|IV|VI|VII|VIII|IX|XI|XII|XIII|XIV|XV|XVI)$/.test(word)) return word;
      if (/^\d/.test(word)) return word;
      return lower.replace(/^\p{L}/u, letter => letter.toUpperCase());
    }).replace(/^CA-a\b/, 'CA-A');
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = format;
  if (typeof window !== 'undefined') window.JournalTitle = { format };
})();
