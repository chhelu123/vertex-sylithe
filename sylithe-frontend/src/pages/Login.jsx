import React, { useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiEye, FiEyeOff } from "react-icons/fi";
import { HiCheckCircle, HiClock, HiMail, HiArrowRight, HiArrowLeft, HiRefresh } from 'react-icons/hi';

import logo from '../assets/treee13.png';
import SEOHead from '../components/SEOHead';
import { useAuth } from '../context/AuthContext';

const ReviewScreen = ({ user }) => (
  <div className="min-h-screen w-full bg-[#FAFAFA] flex flex-col items-center justify-center px-4 font-sans">
    <div className="w-full max-w-[480px]">

      {/* Logo */}
      <div className="flex justify-center mb-10">
        <Link to="/">
          <img src={logo} alt="Sylithe" className="h-12 w-auto object-contain hover:scale-105 transition-transform" />
        </Link>
      </div>

      {/* Status badge */}
      <div className="flex justify-center mb-6">
        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-sm font-semibold">
          <HiClock className="text-amber-500" />
          Application Under Review
        </span>
      </div>

      {/* Heading */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-[#0F172A] mb-3">
          Welcome back, {user.fullName.split(' ')[0]}.
        </h1>
        <p className="text-gray-500 text-base leading-relaxed">
          Your account is currently being reviewed by our team. We'll reach out once you're verified.
        </p>
      </div>

      {/* Timeline card */}
      <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6 shadow-sm">
        <h3 className="text-sm font-bold text-[#0F172A] uppercase tracking-wider mb-5">What's happening</h3>

        <div className="space-y-5">
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-[#16a34a]/10 flex items-center justify-center shrink-0 mt-0.5">
              <HiCheckCircle className="text-[#16a34a] text-lg" />
            </div>
            <div>
              <p className="font-semibold text-[#0F172A] text-sm">Request received</p>
              <p className="text-gray-500 text-sm mt-0.5">We've got your details and you're in the queue.</p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-amber-50 border-2 border-amber-300 flex items-center justify-center shrink-0 mt-0.5">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            </div>
            <div>
              <p className="font-semibold text-[#0F172A] text-sm">Team review in progress</p>
              <p className="text-gray-500 text-sm mt-0.5">Our team verifies every account — typically within 24–48 hours.</p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center shrink-0 mt-0.5">
              <div className="w-2.5 h-2.5 rounded-full bg-gray-300" />
            </div>
            <div>
              <p className="font-semibold text-gray-400 text-sm">Platform access granted</p>
              <p className="text-gray-400 text-sm mt-0.5">You'll get full access to Sylithe's carbon intelligence tools.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Email notice */}
      <div className="flex items-start gap-3 bg-[#F0FDF4] border border-[#BBF7D0] rounded-xl px-5 py-4 mb-8">
        <HiMail className="text-[#16a34a] text-xl shrink-0 mt-0.5" />
        <p className="text-sm text-[#166534] leading-relaxed">
          We'll send a confirmation to <span className="font-semibold">{user.email}</span> as soon as your account is approved.
        </p>
      </div>

      {/* Actions */}
      <div className="space-y-3">
        <Link
          to="/about"
          className="w-full flex items-center justify-center gap-2 bg-[#08292f] text-white py-3.5 rounded-xl font-bold hover:bg-[#062125] transition-all shadow-md active:scale-95 text-[15px]"
        >
          Learn about Sylithe <HiArrowRight />
        </Link>
        <Link
          to="/"
          className="w-full flex items-center justify-center border border-gray-200 text-gray-600 py-3.5 rounded-xl font-semibold hover:bg-gray-50 transition-all text-[15px]"
        >
          Back to Home
        </Link>
      </div>

      <p className="text-center text-sm text-gray-400 mt-8">
        Questions? <a href="mailto:info@sylithe.com" className="text-[#059669] hover:underline">info@sylithe.com</a>
      </p>

    </div>
  </div>
);

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [loggedInUser, setLoggedInUser] = useState(null);

  // Forgot password state
  const [forgotStep, setForgotStep] = useState(0); // 0=login, 1=enter email, 2=enter otp+new pw, 3=done
  const [resetEmail, setResetEmail] = useState('');
  const [resetOtp, setResetOtp] = useState(['', '', '', '', '', '']);
  const [newPassword, setNewPassword] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);
  const otpRefs = useRef([]);

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const startResendCooldown = () => {
    setResendCooldown(60);
    const timer = setInterval(() => {
      setResendCooldown(c => { if (c <= 1) { clearInterval(timer); return 0; } return c - 1; });
    }, 1000);
  };

  const handleForgotSendOtp = async (e) => {
    e.preventDefault();
    setResetLoading(true); setResetError('');
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resetEmail }),
      });
      const data = await res.json();
      if (res.ok) { setForgotStep(2); startResendCooldown(); }
      else setResetError(data.message || 'Failed to send code');
    } catch { setResetError('Could not connect to server.'); }
    finally { setResetLoading(false); }
  };

  const handleResendResetOtp = async () => {
    if (resendCooldown > 0) return;
    setResetLoading(true); setResetError('');
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resetEmail }),
      });
      const data = await res.json();
      if (res.ok) { setResetOtp(['','','','','','']); startResendCooldown(); }
      else setResetError(data.message || 'Failed to resend code');
    } catch { setResetError('Could not connect to server.'); }
    finally { setResetLoading(false); }
  };

  const handleOtpChange = (index, value) => {
    if (!/^\d*$/.test(value)) return;
    const next = [...resetOtp]; next[index] = value.slice(-1); setResetOtp(next);
    if (value && index < 5) otpRefs.current[index + 1]?.focus();
  };

  const handleOtpKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !resetOtp[index] && index > 0) otpRefs.current[index - 1]?.focus();
  };

  const handleOtpPaste = (e) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length === 6) { setResetOtp(pasted.split('')); otpRefs.current[5]?.focus(); }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (newPassword.length < 8) { setResetError('Password must be at least 8 characters'); return; }
    setResetLoading(true); setResetError('');
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resetEmail, password: newPassword }),
      });
      const data = await res.json();
      if (res.ok) { setForgotStep(4); }
      else setResetError(data.message || 'Failed to reset password');
    } catch { setResetError('Could not connect to server.'); }
    finally { setResetLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) {
        login(data.token, data.user);
        navigate('/sylithe');
      } else {
        setError(data.message || 'Login failed. Please try again.');
      }
    } catch {
      setError('Could not connect to server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (loggedInUser) return <ReviewScreen user={loggedInUser} />;

  return (
    <div className="min-h-screen w-full bg-[#FAFAFA] flex flex-col items-center justify-center px-4 font-sans">
      <SEOHead
        title="Log In - Sylithe Carbon Intelligence Platform"
        description="Log in to Sylithe Carbon Intelligence Platform to access your MRV, ICVCM, and carbon monitoring dashboard."
        canonical="https://sylithe.com/login"
      />

      {/* LOGO */}
      <div className="mb-8 flex flex-col items-center">
        <Link to="/">
          <img src={logo} alt="Sylithe Logo" className="h-16 w-auto object-contain mb-6 hover:scale-105 transition-transform" />
        </Link>
        <h1 className="text-3xl font-bold text-[#1a1a1a] tracking-tight">
          {forgotStep === 0 ? 'Log in to Sylithe' : forgotStep === 4 ? 'Password Reset!' : 'Reset Password'}
        </h1>
      </div>

      <div className="w-full max-w-[400px]">

        {/* ── LOGIN FORM ── */}
        {forgotStep === 0 && (
          <>
            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="block text-[15px] font-medium text-[#1a1a1a]">Email</label>
                <input type="email" value={form.email} onChange={update('email')} required
                  className="w-full px-3 py-2.5 bg-[#F1F1F1] border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#1a1a1a] focus:border-[#1a1a1a] transition-all shadow-sm" />
              </div>
              <div className="space-y-2">
                <label className="block text-[15px] font-medium text-[#1a1a1a]">Password</label>
                <div className="relative">
                  <input type={showPassword ? 'text' : 'password'} value={form.password} onChange={update('password')} required
                    className="w-full px-3 py-2.5 bg-[#F1F1F1] border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#1a1a1a] focus:border-[#1a1a1a] transition-all shadow-sm pr-10" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    {showPassword ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                  </button>
                </div>
              </div>
              <div className="text-left">
                <button type="button" onClick={() => { setForgotStep(1); setResetError(''); }}
                  className="text-[15px] text-[#059669] hover:text-[#047857] hover:underline font-medium">
                  Forgot password?
                </button>
              </div>
              {error && <p className="text-red-500 text-sm text-center">{error}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-[#08292f] hover:bg-[#062125] disabled:opacity-60 text-white font-bold py-3 rounded-md transition-colors text-[15px]">
                {loading ? 'Logging in...' : 'Log in'}
              </button>
            </form>
            <div className="mt-8 text-center space-y-4">
              <p className="text-[15px] text-[#1a1a1a]">Don't have an account? <Link to="/signup" className="text-[#059669] hover:text-[#047857] hover:underline">Request access</Link></p>
              <p className="text-[15px] text-[#1a1a1a]">Need help? <a href="mailto:info@sylithe.com" className="text-[#059669] hover:text-[#047857] hover:underline">Contact Support</a></p>
            </div>
          </>
        )}

        {/* ── FORGOT STEP 1: Enter email ── */}
        {forgotStep === 1 && (
          <>
            <p className="text-gray-500 text-sm text-center mb-8">Enter your account email and we'll send a reset code.</p>
            <form className="space-y-5" onSubmit={handleForgotSendOtp}>
              <div className="space-y-2">
                <label className="block text-[15px] font-medium text-[#1a1a1a]">Email</label>
                <input type="email" value={resetEmail} onChange={e => setResetEmail(e.target.value)} required
                  placeholder="name@company.com"
                  className="w-full px-3 py-2.5 bg-[#F1F1F1] border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#1a1a1a] focus:border-[#1a1a1a] transition-all shadow-sm" />
              </div>
              {resetError && <p className="text-red-500 text-sm text-center">{resetError}</p>}
              <button type="submit" disabled={resetLoading}
                className="w-full bg-[#08292f] hover:bg-[#062125] disabled:opacity-60 text-white font-bold py-3 rounded-md transition-colors text-[15px] flex items-center justify-center gap-2">
                {resetLoading ? 'Sending...' : <> Send Reset Code <HiArrowRight /> </>}
              </button>
              <button type="button" onClick={() => { setForgotStep(0); setResetError(''); }}
                className="w-full flex items-center justify-center gap-1 text-gray-500 hover:text-gray-700 text-sm mt-2">
                <HiArrowLeft /> Back to login
              </button>
            </form>
          </>
        )}

        {/* ── FORGOT STEP 2: Enter OTP ── */}
        {forgotStep === 2 && (
          <>
            <div className="text-center mb-6">
              <div className="w-14 h-14 rounded-full bg-[#FFF7ED] border-2 border-[#fed7aa] flex items-center justify-center mx-auto mb-3">
                <HiMail className="text-2xl text-[#c2410c]" />
              </div>
              <p className="text-gray-500 text-sm">We sent a 6-digit code to <span className="font-semibold text-[#0F172A]">{resetEmail}</span></p>
            </div>
            <form className="space-y-5" onSubmit={async e => {
              e.preventDefault();
              if (resetOtp.join('').length < 6) { setResetError('Please enter the full 6-digit code'); return; }
              setResetLoading(true); setResetError('');
              try {
                const res = await fetch(`${import.meta.env.VITE_API_URL}/api/verify-reset-otp`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ email: resetEmail, otp: resetOtp.join('') }),
                });
                const data = await res.json();
                if (res.ok) setForgotStep(3);
                else setResetError(data.message || 'Incorrect code');
              } catch { setResetError('Could not connect to server.'); }
              finally { setResetLoading(false); }
            }}>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-3 text-center">Enter reset code</label>
                <div className="flex gap-3 justify-center" onPaste={handleOtpPaste}>
                  {resetOtp.map((digit, i) => (
                    <input key={i} ref={el => (otpRefs.current[i] = el)} type="text" inputMode="numeric" maxLength={1}
                      value={digit} onChange={e => handleOtpChange(i, e.target.value)} onKeyDown={e => handleOtpKeyDown(i, e)}
                      className={`w-11 h-13 text-center text-xl font-bold rounded-xl border-2 outline-none transition-all
                        ${digit ? 'border-[#c2410c] bg-[#FFF7ED] text-[#c2410c]' : 'border-gray-300 bg-white'}
                        focus:border-[#f97316] focus:ring-2 focus:ring-[#f97316]/30`} />
                  ))}
                </div>
              </div>
              {resetError && <p className="text-red-500 text-sm text-center">{resetError}</p>}
              <button type="submit" disabled={resetOtp.join('').length < 6 || resetLoading}
                className="w-full bg-[#08292f] hover:bg-[#062125] disabled:opacity-60 text-white font-bold py-3 rounded-md transition-colors text-[15px] flex items-center justify-center gap-2">
                {resetLoading ? 'Verifying...' : <> Continue <HiArrowRight /> </>}
              </button>
              <div className="flex items-center justify-between text-sm">
                <button type="button" onClick={() => { setForgotStep(1); setResetError(''); }} className="flex items-center gap-1 text-gray-500 hover:text-gray-700">
                  <HiArrowLeft /> Back
                </button>
                <button type="button" onClick={handleResendResetOtp} disabled={resendCooldown > 0 || resetLoading}
                  className="flex items-center gap-1 text-[#059669] hover:underline disabled:text-gray-400 disabled:no-underline">
                  <HiRefresh className={resetLoading ? 'animate-spin' : ''} />
                  {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ── FORGOT STEP 3: Enter new password ── */}
        {forgotStep === 3 && (
          <>
            <p className="text-gray-500 text-sm text-center mb-6">Enter your new password below.</p>
            <form className="space-y-5" onSubmit={handleResetPassword}>
              <div className="space-y-2">
                <label className="block text-[15px] font-medium text-[#1a1a1a]">New Password</label>
                <div className="relative">
                  <input type={showNewPassword ? 'text' : 'password'} value={newPassword} onChange={e => setNewPassword(e.target.value)}
                    required minLength={8} placeholder="Min. 8 characters"
                    className="w-full px-3 py-2.5 bg-[#F1F1F1] border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#1a1a1a] focus:border-[#1a1a1a] transition-all shadow-sm pr-10" />
                  <button type="button" onClick={() => setShowNewPassword(!showNewPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    {showNewPassword ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                  </button>
                </div>
              </div>
              {resetError && <p className="text-red-500 text-sm text-center">{resetError}</p>}
              <button type="submit" disabled={resetLoading || !newPassword}
                className="w-full bg-[#08292f] hover:bg-[#062125] disabled:opacity-60 text-white font-bold py-3 rounded-md transition-colors text-[15px]">
                {resetLoading ? 'Resetting...' : 'Reset Password'}
              </button>
              <button type="button" onClick={() => { setForgotStep(2); setResetError(''); }}
                className="w-full flex items-center justify-center gap-1 text-gray-500 hover:text-gray-700 text-sm">
                <HiArrowLeft /> Back
              </button>
            </form>
          </>
        )}

        {/* ── FORGOT STEP 4: Success ── */}
        {forgotStep === 4 && (
          <div className="text-center">
            <div className="w-16 h-16 rounded-full bg-[#16a34a]/10 flex items-center justify-center mx-auto mb-5">
              <HiCheckCircle className="text-5xl text-[#16a34a]" />
            </div>
            <p className="text-gray-500 text-sm mb-8">Your password has been reset successfully. You can now log in with your new password.</p>
            <button onClick={() => { setForgotStep(0); setResetEmail(''); setResetOtp(['','','','','','']); setNewPassword(''); setResetError(''); setError(''); }}
              className="w-full bg-[#08292f] hover:bg-[#062125] text-white font-bold py-3 rounded-md transition-colors text-[15px]">
              Back to Login
            </button>
          </div>
        )}

      </div>
    </div>
  );
};

export default Login;
