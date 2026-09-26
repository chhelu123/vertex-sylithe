import React from 'react';
import SEOHead from '../components/SEOHead';

const PrivacyPolicy = () => {
    return (
        <div className="pt-32 pb-24 px-6 md:px-12 lg:px-24 max-w-4xl mx-auto font-sans text-slate-800">
            <SEOHead
                title="Privacy Policy | Sylithe"
                description="Learn how Sylithe collects, uses, and protects your personal information. Read our privacy practices and data handling policies."
                path="/privacy-policy"
            />
            <h1 className="text-4xl md:text-5xl font-bold mb-6 text-[#0F172A]">Privacy Policy</h1>
            <p className="text-sm text-slate-500 mb-12 uppercase tracking-widest font-bold">Last updated: January 2026</p>

            <div className="space-y-8 leading-relaxed">
                <p>Your privacy is important to us. This Privacy Policy describes how Sylithe collects, uses, and protects your personal information. Please also review our Terms of Service.</p>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">1. Introduction</h2>
                    <p>Sylithe Technologies Private Limited ("Sylithe", "we", "us", or "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, and safeguard your information when you visit our website www.sylithe.com (the "Site"). By accessing or using our Site, you agree to the terms of this Privacy Policy. If you do not agree, please do not use the Site.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">2. Information We Collect</h2>
                    <p>We may collect several types of information from our users. This includes information you voluntarily provide through contact forms or inquiries, automatically collected information such as browser type, device information, and IP address, as well as cookies and similar technologies to improve your browsing experience.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">3. How We Use Your Information</h2>
                    <p>We use collected information to respond to your inquiries, improve our Site and services, comply with legal obligations, and protect against unauthorized access or misuse.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">4. Cookies</h2>
                    <p>We may use cookies to enhance your experience on our Site. You can control cookie settings through your browser. Disabling cookies may affect certain features of the Site.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">5. Data Sharing</h2>
                    <p>We do not sell your personal information. We may share information with service providers who assist in operating our Site, when required by law or legal process, to protect our rights or the safety of others, and in connection with a business transfer or acquisition.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">6. Data Security</h2>
                    <p>We implement reasonable security measures to protect your information. However, no method of transmission over the Internet is completely secure, and we cannot guarantee absolute security.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">7. Your Rights</h2>
                    <p>You may have rights regarding your personal information, including the right to access, correct, or delete your data. To exercise these rights, please contact us at info@sylithe.com.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">8. Third-Party Links</h2>
                    <p>Our Site may contain links to third-party websites. We are not responsible for the privacy practices of these external sites.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">9. Changes to This Policy</h2>
                    <p>We may update this Privacy Policy from time to time. Changes will be posted on this page with an updated date. Continued use of the Site constitutes acceptance of any changes.</p>
                </section>

                <section>
                    <h2 className="text-2xl font-bold text-[#0F172A] mb-4">10. Contact Us</h2>
                    <p className="mb-4">For questions about this Privacy Policy, contact us at:</p>
                    <address className="not-italic bg-gray-50 p-6 rounded-xl border border-gray-200">
                        <strong>Sylithe Technologies Private Limited</strong><br />

                        Email: <a href="mailto:info@sylithe.com" className="text-sylitheGreen hover:underline font-bold">info@sylithe.com</a>
                    </address>
                </section>
            </div>
        </div>
    );
};

export default PrivacyPolicy;
