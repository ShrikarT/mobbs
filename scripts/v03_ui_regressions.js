/**
 * Focused deterministic regression suite for V03-U1 Six Review Findings
 */
import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('=== RUNNING V03-U1 FOCUSED REGRESSIONS ===\n');

// 1. Contrast calculations (Finding 6)
function lum(hex) {
  const rgb = hex.replace('#', '').match(/.{2}/g).map((x) => parseInt(x, 16) / 255);
  const a = rgb.map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
}

function contrast(c1, c2) {
  const l1 = lum(c1), l2 = lum(c2);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

console.log('1. Testing WCAG Contrast Ratios (Criterion 5 / Finding 6)...');
const cTextPrimary = '#17211f';
const cTextMuted = '#53615b';
const cTextSubtle = '#485651';
const cBgCanvas = '#f6f4ef';
const cBgSubtle = '#f0ede6';
const cBgSurface = '#ffffff';

const cr1 = contrast(cTextPrimary, cBgSurface); // persona-id on pending node
const cr2 = contrast(cTextSubtle, cBgSurface);  // indicator-pending on pending node
const cr3 = contrast(cTextSubtle, cBgSubtle);   // score-reason / act-reason on unavailable item
const cr4 = contrast(cTextSubtle, cBgCanvas);   // quote-heading on canvas

console.log(`  - persona-id on pending node: ${cr1.toFixed(2)}:1 (threshold >= 4.5:1)`);
console.log(`  - indicator-pending on pending node: ${cr2.toFixed(2)}:1 (threshold >= 4.5:1)`);
console.log(`  - score-reason / act-reason on unavailable item: ${cr3.toFixed(2)}:1 (threshold >= 4.5:1)`);
console.log(`  - text-subtle on bg-canvas: ${cr4.toFixed(2)}:1 (threshold >= 4.5:1)`);

assert(cr1 >= 4.5, `persona-id contrast ${cr1} < 4.5`);
assert(cr2 >= 4.5, `indicator-pending contrast ${cr2} < 4.5`);
assert(cr3 >= 4.5, `unavailable item contrast ${cr3} < 4.5`);
assert(cr4 >= 4.5, `canvas text contrast ${cr4} < 4.5`);

// Verify opacity removed from pending and unavailable in style.css
const css = fs.readFileSync(path.join(__dirname, '../apps/web/src/style.css'), 'utf8');
assert(!css.includes('.persona-node.pending {\n  opacity:'), 'opacity still present on .persona-node.pending');
assert(!css.includes('.score-item.unavailable {\n  opacity:'), 'opacity still present on .score-item.unavailable');
assert(!css.includes('.engagement-item.unavailable {\n  opacity:'), 'opacity still present on .engagement-item.unavailable');
console.log('  ✓ Contrast and opacity regression passed.\n');

// 2. Finding 1: Removal of fabricated report statements & truthful disclosure
console.log('2. Testing Source Verification of Report Narratives (Finding 1)...');
const appTsx = fs.readFileSync(path.join(__dirname, '../apps/web/src/App.tsx'), 'utf8');

assert(!appTsx.includes('Observed retention drop occurred at Scene 2 (3.0s – 8.0s)'), 'Fabricated Scene 2 / 3-8s statement still found in App.tsx');
assert(!appTsx.includes('statistical support threshold'), 'Fabricated statistical support threshold statement still found in App.tsx');
assert(appTsx.includes('deterministic stop-fraction detector'), 'Missing reference to deterministic stop-fraction detector');

// Verify disclosure gating: only Flash 50 gets the 5-archetype disclosure
assert(appTsx.includes("(report.cast.profile === 'flash' || report.manifest?.profile === 'flash') && (report.cast.requested === 50 || report.manifest?.requested === 50)"), 'Disclosure gating for Flash 50 missing');
assert(appTsx.includes('The {report.cast.profile === \'test\' ? \'Test 3\' : `${report.cast.profile} ${report.cast.requested}`} cast uses {report.cast.effective} simulated personas'), 'Truthful non-flash disclosure missing');
console.log('  ✓ Finding 1 narrative and disclosure regression passed.\n');

// 3. Finding 2: Persisted event reason binding
console.log('3. Testing Event Emitter Persisted Reason Binding (Finding 2)...');
assert(!appTsx.includes('{p.drop_reason && <span className="ev-reason">reason: {p.drop_reason}</span>}'), 'Old drop_reason binding still in ordered log');
assert(appTsx.includes('{p.reason && ('), 'Missing p.reason check in event log');
assert(appTsx.includes('{isStop ? \'stop quote: \' : \'quote: \'}&ldquo;{p.reason}&rdquo;'), 'Missing stop quote vs quote distinction in event log');
console.log('  ✓ Finding 2 emitter payload reason regression passed.\n');

// 4. Finding 3: Async state fencing and request cancellation
console.log('4. Testing Async Fencing and Cancellation (Finding 3)...');
assert(appTsx.includes('const runFenceRef = useRef<number>(0);'), 'Missing runFenceRef');
assert(appTsx.includes('const evidenceFenceRef = useRef<number>(0);'), 'Missing evidenceFenceRef');
assert(appTsx.includes('const delFenceRef = useRef<number>(0);'), 'Missing delFenceRef');
assert(appTsx.includes('const pollAbortControllerRef = useRef<AbortController | null>(null);'), 'Missing pollAbortControllerRef');
assert(appTsx.includes('abortCtrl.abort()'), 'Missing abortCtrl.abort on cleanup');
assert(appTsx.includes("if (err.name === 'AbortError' || !isMounted || runFenceRef.current !== currentFence)"), 'Missing fence/abort check in catch block');
console.log('  ✓ Finding 3 async fencing and cancellation regression passed.\n');

// 5. Finding 4: Accessible keyboard-operable evidence quotes
console.log('5. Testing Semantic Controls and Keyboard Accessibility for Quotes (Finding 4)...');
assert(appTsx.includes('className="quote-button"'), 'Quote buttons missing semantic class');
assert(appTsx.includes('type="button"'), 'Quote controls are not semantic buttons');
assert(appTsx.includes('aria-label={`Inspect evidence quote'), 'Quote button missing accessible aria-label');
assert(appTsx.includes("if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' '))"), 'Parent note card missing e.target === e.currentTarget containment');
console.log('  ✓ Finding 4 keyboard accessibility regression passed.\n');

// 6. Finding 5: Cohort coverage and legacy field handling
console.log('6. Testing Cohort Coverage and Legacy Field Fallbacks (Finding 5)...');
assert(appTsx.includes('className="cohort-coverage-card"'), 'Cohort coverage card missing');
assert(appTsx.includes('Partial cohort:'), 'Partial cohort alert missing');
assert(appTsx.includes('report.coverage?.excluded_traces'), 'Excluded traces rendering missing');
assert(appTsx.includes('Quality indices unavailable: report does not contain score indices.'), 'Legacy scores fallback missing');
assert(appTsx.includes('Engagement telemetry unavailable: report does not contain action telemetry.'), 'Legacy engagement fallback missing');
assert(appTsx.includes('Scene retention curve unavailable: report does not contain retention intervals.'), 'Legacy retention fallback missing');
console.log('  ✓ Finding 5 cohort coverage and legacy fallback regression passed.\n');

console.log('=== ALL 6 FOCUSED REGRESSIONS PASSED ===\n');
