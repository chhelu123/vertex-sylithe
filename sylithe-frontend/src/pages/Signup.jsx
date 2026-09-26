import React, { useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { HiArrowRight, HiArrowLeft, HiCheckCircle, HiMail, HiRefresh } from 'react-icons/hi';
import HCaptcha from '@hcaptcha/react-hcaptcha';

import authBg from '../assets/tree23.png';
import logo from '../assets/treee13.png';
import SEOHead from '../components/SEOHead';

const inputClass = "w-full px-4 py-3 rounded-lg border border-gray-300 bg-white focus:ring-2 focus:ring-[#A3E635] focus:border-transparent outline-none transition-all text-[#0F172A]";
const labelClass = "block text-sm font-semibold text-gray-700 mb-1";
const selectClass = "w-full px-4 py-3 rounded-lg border border-gray-300 bg-white focus:ring-2 focus:ring-[#A3E635] focus:border-transparent outline-none transition-all text-[#0F172A] appearance-none";

const INTEREST_OPTIONS_BY_ACTIVITY = {
  project_developer: [
    { value: 'pre_issuance_mrv',    label: 'Pre-issuance MRV & verification' },
    { value: 'project_development', label: 'Project development tools' },
    { value: 'biomass_mapping',     label: 'Biomass & canopy mapping' },
    { value: 'compliance',          label: 'ICVCM / Verra compliance' },
    { value: 'exploring',           label: 'Just exploring' },
  ],
  consultancy: [
    { value: 'pre_issuance_mrv',    label: 'Pre-issuance MRV & verification' },
    { value: 'risk_analysis',       label: 'Credit risk analysis & scoring' },
    { value: 'portfolio_monitoring',label: 'Portfolio monitoring' },
    { value: 'compliance',          label: 'ICVCM / Verra compliance' },
    { value: 'exploring',           label: 'Just exploring' },
  ],
  corporate_sustainability: [
    { value: 'portfolio_monitoring',label: 'Portfolio monitoring' },
    { value: 'risk_analysis',       label: 'Credit risk analysis & scoring' },
    { value: 'compliance',          label: 'ICVCM / Verra compliance' },
    { value: 'exploring',           label: 'Just exploring' },
  ],
  research: [
    { value: 'pre_issuance_mrv',    label: 'Pre-issuance MRV & verification' },
    { value: 'biomass_mapping',     label: 'Biomass & canopy mapping' },
    { value: 'exploring',           label: 'Just exploring' },
  ],
  other: [
    { value: 'pre_issuance_mrv',    label: 'Pre-issuance MRV & verification' },
    { value: 'risk_analysis',       label: 'Credit risk analysis & scoring' },
    { value: 'portfolio_monitoring',label: 'Portfolio monitoring' },
    { value: 'project_development', label: 'Project development tools' },
    { value: 'biomass_mapping',     label: 'Biomass & canopy mapping' },
    { value: 'compliance',          label: 'ICVCM / Verra compliance' },
    { value: 'exploring',           label: 'Just exploring' },
  ],
};

const PROJECT_TYPE_OPTIONS = [
  { value: 'arr',     label: 'ARR' },
  { value: 'redd',    label: 'REDD+' },
  { value: 'biochar', label: 'Biochar' },
];

const API = import.meta.env.VITE_API_URL;

const Signup = () => {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    fullName: '', email: '', mobile: '', password: '', confirmPassword: '',
    companyName: '', designation: '', primaryActivity: '',
    projectType: '', companySize: '', interestArea: '', hearAbout: '',
  });
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [error, setError] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const otpRefs = useRef([]);
  const captchaRef = useRef(null);
  const navigate = useNavigate();

  const update = (field) => (e) => {
    const value = e.target.value;
    if (field === 'primaryActivity') {
      // Project type only applies to developers, so drop it when they switch away
      setForm({ ...form, primaryActivity: value, interestArea: '', projectType: '' });
    } else {
      setForm({ ...form, [field]: value });
    }
  };

  // ── Step 1 → send OTP ────────────────────────────────────────────────────
  const handleSendOtp = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirmPassword) { setError('Passwords do not match'); return; }
    if (form.password.length < 8) { setError('Password must be at least 8 characters'); return; }
    if (!captchaToken) { setError('Please complete the captcha'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API}/api/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.email, name: form.fullName, captchaToken }),
      });
      const data = await res.json();
      if (res.ok) {
        setStep(2);
        startResendCooldown();
      } else {
        setError(data.message || 'Failed to send OTP');
        captchaRef.current?.resetCaptcha();
        setCaptchaToken('');
      }
    } catch {
      setError('Could not connect to server. Please try again.');
      captchaRef.current?.resetCaptcha();
      setCaptchaToken('');
    } finally {
      setLoading(false);
    }
  };

  const startResendCooldown = () => {
    setResendCooldown(60);
    const timer = setInterval(() => {
      setResendCooldown((c) => { if (c <= 1) { clearInterval(timer); return 0; } return c - 1; });
    }, 1000);
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0) return;
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API}/api/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.email, name: form.fullName }),
      });
      const data = await res.json();
      if (res.ok) { setOtp(['','','','','','']); startResendCooldown(); }
      else setError(data.message || 'Failed to resend OTP');
    } catch {
      setError('Could not connect to server.');
    } finally {
      setLoading(false);
    }
  };

  // ── OTP input handlers ───────────────────────────────────────────────────
  const handleOtpChange = (index, value) => {
    if (!/^\d*$/.test(value)) return;
    const newOtp = [...otp];
    newOtp[index] = value.slice(-1);
    setOtp(newOtp);
    if (value && index < 5) otpRefs.current[index + 1]?.focus();
  };

  const handleOtpKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpPaste = (e) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length === 6) {
      setOtp(pasted.split(''));
      otpRefs.current[5]?.focus();
    }
  };

  // ── Step 2 → verify OTP ──────────────────────────────────────────────────
  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    const code = otp.join('');
    if (code.length < 6) { setError('Please enter the full 6-digit code'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API}/api/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.email, otp: code }),
      });
      const data = await res.json();
      if (res.ok) { setStep(3); }
      else setError(data.message || 'Incorrect code');
    } catch {
      setError('Could not connect to server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // ── Step 3 → final signup ────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API}/api/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) { setStep(4); }
      else setError(data.message || 'Something went wrong');
    } catch {
      setError('Could not connect to server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const totalSteps = 3;
  const progressStep = Math.min(step, totalSteps);

  return (
    <div className="min-h-screen w-full flex bg-[#F1F1F1] font-sans">
      <SEOHead
        title="Sign Up - Sylithe Carbon Intelligence Platform"
        description="Join leading organizations using Sylithe's science-backed platform to measure, reduce, and report carbon emissions with satellite precision."
        canonical="https://sylithe.com/signup"
      />

      {/* LEFT PANEL */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden bg-[#0F172A]">
        <div className="absolute inset-0 z-0">
          <img src={authBg} alt="Background" className="w-full h-full object-cover opacity-60" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#022c22] via-transparent to-transparent" />
        </div>
        <div className="relative z-10 p-16 flex flex-col justify-between h-full text-white">
          <div className="flex items-center gap-2">
            <img src={logo} alt="Sylithe" className="h-8 w-auto mix-blend-screen" />
            <span className="text-xl font-bold tracking-tight">Sylithe</span>
          </div>
          <div className="mb-10">
            <h2 className="text-4xl font-bold leading-tight mb-6">
              Start your journey to <br />
              <span className="text-[#A3E635]">confident climate action.</span>
            </h2>
            <p className="text-gray-300 text-lg leading-relaxed max-w-md">
              Join leading organizations using Sylithe's science-backed platform to measure, reduce, and report carbon emissions with satellite precision.
            </p>
            <div className="mt-8 flex gap-2">
              {[1, 2, 3].map((s) => (
                <div key={s} className={`h-1 w-12 rounded-full transition-all ${progressStep >= s ? 'bg-[#A3E635]' : 'bg-white/20'}`} />
              ))}
            </div>
            <p className="text-gray-400 text-sm mt-3">
              {step === 1 && 'Step 1 of 3 — Account details'}
              {step === 2 && 'Step 2 of 3 — Verify your email'}
              {step === 3 && 'Step 3 of 3 — About your work'}
              {step === 4 && 'All done!'}
            </p>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 md:p-16 overflow-y-auto">
        <div className="max-w-md w-full">

          {/* ── STEP 1: Account details ── */}
          {step === 1 && (
            <>
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-[#0F172A] mb-2">Create your account</h2>
                <p className="text-gray-500">Tell us a bit about yourself to get started.</p>
              </div>
              <form className="space-y-5" onSubmit={handleSendOtp}>
                <div>
                  <label className={labelClass}>Full Name</label>
                  <input type="text" placeholder="Your name" value={form.fullName} onChange={update('fullName')} className={inputClass} required />
                </div>
                <div>
                  <label className={labelClass}>Work Email</label>
                  <input type="email" placeholder="name@company.com" value={form.email} onChange={update('email')} className={inputClass} required />
                </div>
                <div>
                  <label className={labelClass}>Mobile Number</label>
                  <input type="tel" placeholder="+91 98765 43210" value={form.mobile} onChange={update('mobile')} className={inputClass} required />
                </div>
                <div>
                  <label className={labelClass}>Password</label>
                  <input type="password" placeholder="Min. 8 characters" value={form.password} onChange={update('password')} className={inputClass} required minLength={8} />
                </div>
                <div>
                  <label className={labelClass}>Confirm Password</label>
                  <input type="password" placeholder="Re-enter your password" value={form.confirmPassword} onChange={update('confirmPassword')} className={inputClass} required minLength={8} />
                </div>
                <div className="flex items-center gap-2">
                  <input type="checkbox" id="terms" className="w-4 h-4 border-gray-300 rounded focus:ring-[#A3E635]" required />
                  <label htmlFor="terms" className="text-sm text-gray-600">
                    I agree to the <Link to="/terms-of-service" className="underline hover:text-black">Terms</Link> and <Link to="/privacy-policy" className="underline hover:text-black">Privacy Policy</Link>.
                  </label>
                </div>
                <div className="flex justify-center">
                  <HCaptcha
                    sitekey={import.meta.env.VITE_HCAPTCHA_SITE_KEY}
                    onVerify={(token) => setCaptchaToken(token)}
                    onExpire={() => setCaptchaToken('')}
                    ref={captchaRef}
                  />
                </div>
                {error && <p className="text-red-500 text-sm text-center">{error}</p>}
                <button type="submit" disabled={loading || !captchaToken} className="w-full bg-[#08292f] text-white py-3.5 rounded-lg font-bold hover:bg-[#062125] transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2 disabled:opacity-60">
                  {loading ? 'Sending code...' : <> Continue <HiArrowRight /> </>}
                </button>
              </form>
            </>
          )}

          {/* ── STEP 2: OTP Verification ── */}
          {step === 2 && (
            <>
              <div className="text-center mb-8">
                <div className="w-16 h-16 rounded-full bg-[#F0FDF4] border-2 border-[#A3E635] flex items-center justify-center mx-auto mb-4">
                  <HiMail className="text-3xl text-[#16a34a]" />
                </div>
                <h2 className="text-3xl font-bold text-[#0F172A] mb-2">Check your email</h2>
                <p className="text-gray-500 text-sm">
                  We sent a 6-digit code to <span className="font-semibold text-[#0F172A]">{form.email}</span>
                </p>
              </div>

              <form className="space-y-6" onSubmit={handleVerifyOtp}>
                {/* OTP boxes */}
                <div>
                  <label className={labelClass + ' text-center block mb-3'}>Enter verification code</label>
                  <div className="flex gap-3 justify-center" onPaste={handleOtpPaste}>
                    {otp.map((digit, i) => (
                      <input
                        key={i}
                        ref={(el) => (otpRefs.current[i] = el)}
                        type="text"
                        inputMode="numeric"
                        maxLength={1}
                        value={digit}
                        onChange={(e) => handleOtpChange(i, e.target.value)}
                        onKeyDown={(e) => handleOtpKeyDown(i, e)}
                        className={`w-12 h-14 text-center text-2xl font-bold rounded-xl border-2 outline-none transition-all
                          ${digit ? 'border-[#16a34a] bg-[#F0FDF4] text-[#15803d]' : 'border-gray-300 bg-white text-[#0F172A]'}
                          focus:border-[#A3E635] focus:ring-2 focus:ring-[#A3E635]/30`}
                      />
                    ))}
                  </div>
                </div>

                <p className="text-xs text-gray-400 text-center">
                  Code expires in 10 minutes. Check spam if you don't see it.
                </p>

                {error && <p className="text-red-500 text-sm text-center">{error}</p>}

                <button type="submit" disabled={loading || otp.join('').length < 6} className="w-full bg-[#08292f] text-white py-3.5 rounded-lg font-bold hover:bg-[#062125] transition-all shadow-lg active:scale-95 disabled:opacity-60">
                  {loading ? 'Verifying...' : 'Verify Email'}
                </button>

                <div className="flex items-center justify-between text-sm">
                  <button type="button" onClick={() => { setStep(1); setError(''); }} className="flex items-center gap-1 text-gray-500 hover:text-gray-700">
                    <HiArrowLeft /> Back
                  </button>
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    disabled={resendCooldown > 0 || loading}
                    className="flex items-center gap-1 text-[#16a34a] hover:underline disabled:text-gray-400 disabled:no-underline"
                  >
                    <HiRefresh className={loading ? 'animate-spin' : ''} />
                    {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                  </button>
                </div>
              </form>
            </>
          )}

          {/* ── STEP 3: Work details ── */}
          {step === 3 && (
            <>
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-[#0F172A] mb-2">Tell us about your work</h2>
                <p className="text-gray-500">This helps us tailor the platform to your needs.</p>
              </div>
              <form className="space-y-5" onSubmit={handleSubmit}>
                <div>
                  <label className={labelClass}>Company / Organisation Name</label>
                  <input type="text" placeholder="Acme Corp" value={form.companyName} onChange={update('companyName')} className={inputClass} required />
                </div>
                <div>
                  <label className={labelClass}>Your Designation</label>
                  <input type="text" placeholder="e.g. Sustainability Lead, CTO, Analyst" value={form.designation} onChange={update('designation')} className={inputClass} required />
                </div>
                <div>
                  <label className={labelClass}>What does your organisation primarily do?</label>
                  <select value={form.primaryActivity} onChange={update('primaryActivity')} className={selectClass} required>
                    <option value="" disabled>Select one</option>
                    <option value="project_developer">Develop carbon / forestry projects</option>
                    <option value="consultancy">Sustainability consultancy</option>
                    <option value="corporate_sustainability">Corporate sustainability / ESG</option>
                    <option value="research">Research / academia</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                {/* Only project developers are asked what they actually develop */}
                {form.primaryActivity === 'project_developer' && (
                  <div>
                    <label className={labelClass}>Your project type</label>
                    <select value={form.projectType} onChange={update('projectType')} className={selectClass} required>
                      <option value="" disabled>Select one</option>
                      {PROJECT_TYPE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label className={labelClass}>Company Size</label>
                  <select value={form.companySize} onChange={update('companySize')} className={selectClass} required>
                    <option value="" disabled>Select one</option>
                    <option value="1-10">1–10 employees</option>
                    <option value="11-50">11–50 employees</option>
                    <option value="51-200">51–200 employees</option>
                    <option value="201-1000">201–1,000 employees</option>
                    <option value="1000+">1,000+ employees</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>What are you most interested in?</label>
                  <select value={form.interestArea} onChange={update('interestArea')} className={selectClass} required disabled={!form.primaryActivity}>
                    <option value="" disabled>
                      {form.primaryActivity ? 'Select one' : 'Select your organisation type first'}
                    </option>
                    {(INTEREST_OPTIONS_BY_ACTIVITY[form.primaryActivity] || []).map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelClass}>How did you hear about Sylithe?</label>
                  <select value={form.hearAbout} onChange={update('hearAbout')} className={selectClass}>
                    <option value="" disabled>Select one</option>
                    <option value="search">Search engine</option>
                    <option value="linkedin">LinkedIn</option>
                    <option value="referral">Referral / word of mouth</option>
                    <option value="event">Conference / event</option>
                    <option value="news">News / media</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="flex gap-3">
                  <button type="button" onClick={() => setStep(2)} className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-lg border border-gray-300 font-bold text-gray-700 hover:bg-gray-50 transition-all">
                    <HiArrowLeft /> Back
                  </button>
                  <button type="submit" disabled={loading} className="flex-1 bg-[#08292f] text-white py-3.5 rounded-lg font-bold hover:bg-[#062125] transition-all shadow-lg active:scale-95 disabled:opacity-60">
                    {loading ? 'Creating account...' : 'Create Account'}
                  </button>
                </div>
                {error && <p className="text-red-500 text-sm text-center mt-2">{error}</p>}
              </form>
            </>
          )}

          {/* ── STEP 4: Success ── */}
          {step === 4 && (
            <div className="text-center">
              <div className="w-20 h-20 rounded-full bg-[#16a34a]/10 flex items-center justify-center mx-auto mb-6">
                <HiCheckCircle className="text-5xl text-[#16a34a]" />
              </div>
              <h2 className="text-3xl font-bold text-[#0F172A] mb-3">You're in!</h2>
              <p className="text-gray-600 text-base leading-relaxed mb-6">
                Welcome, <span className="font-semibold text-[#0F172A]">{form.fullName}</span>. Your account is ready with <span className="font-semibold text-[#15803d]">Free Tier access</span>.
              </p>

              {/* Free tier info */}
              <div className="bg-[#F0FDF4] border border-[#bbf7d0] rounded-xl p-5 text-left mb-4">
                <p className="text-sm font-bold text-[#15803d] mb-3">What you can access now:</p>
                <p className="text-sm text-gray-600 flex items-start gap-2 mb-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] mt-1.5 shrink-0" />
                  Project Registry — first 5 Verra VCS & 5 Gold Standard India projects
                </p>
                <p className="text-sm text-gray-600 flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] mt-1.5 shrink-0" />
                  Basic project profiles, status and registry links
                </p>
              </div>

              {/* Upgrade CTA */}
              <div className="bg-[#FFF7ED] border border-[#fed7aa] rounded-xl p-5 text-left mb-6">
                <p className="text-sm font-bold text-[#c2410c] mb-3">Want full access?</p>
                <p className="text-sm text-gray-600 mb-3">
                  Contact our team to upgrade to Pro — unlock CHM, LULC, AGB analysis, full registry and automated MRV reports.
                </p>
                <a
                  href={`mailto:info@sylithe.com?subject=Upgrade to Pro - ${form.fullName}&body=Hi Sylithe team, I'd like to upgrade my account (${form.email}) to Pro access.`}
                  className="inline-flex items-center gap-2 text-sm font-bold text-[#c2410c] hover:underline"
                >
                  <HiMail /> info@sylithe.com
                </a>
              </div>

              <div className="flex flex-col gap-3">
                <Link to="/login" className="w-full bg-[#08292f] text-white py-3.5 rounded-lg font-bold hover:bg-[#062125] transition-all shadow-lg active:scale-95 text-center">
                  Log in to Sylithe
                </Link>
                <Link to="/" className="w-full border border-gray-300 text-gray-700 py-3.5 rounded-lg font-bold hover:bg-gray-50 transition-all text-center">
                  Back to Home
                </Link>
              </div>
            </div>
          )}

          {step !== 4 && (
            <p className="text-center text-sm text-gray-600 mt-8">
              Already have an account? <Link to="/login" className="font-bold text-[#0F172A] hover:underline">Log in</Link>
            </p>
          )}

        </div>
      </div>
    </div>
  );
};

export default Signup;
