import React from 'react';
import { IMAGES } from '../theme';
import { CtaBand, Eyebrow } from '../components';

export default function About() {
  return (
    <>
      <section className="mx-auto max-w-7xl px-5 lg:px-8 pt-20 pb-12">
        <Eyebrow>About Sylithe</Eyebrow>
        <h1 className="font-display font-light text-5xl md:text-7xl leading-[1.03] mt-4 max-w-5xl">
          We believe climate finance should be as rigorous as the science it pays for.
        </h1>
      </section>
      <section className="mx-auto max-w-7xl px-5 lg:px-8">
        <img src={IMAGES.mangroves} alt="Mangrove coastline" className="w-full h-[420px] object-cover object-bottom rounded-3xl" />
      </section>
      <section className="mx-auto max-w-7xl px-5 lg:px-8 py-24 grid lg:grid-cols-2 gap-14 text-lg leading-relaxed text-[#3A3D36]">
        <div className="space-y-5">
          <p>Sylithe began with satellite monitoring of land and forests: measuring canopy height, land-use history and biomass for carbon projects across India.</p>
          <p>That work kept surfacing the same problem. Companies and buyers make big climate decisions on claims that are hard to check, like a baseline in a 200-page PDF, a footnote in an annual report, or an issuance nobody compared with the original estimate.</p>
        </div>
        <div className="space-y-5">
          <p>So we built an intelligence layer that does the reading. AI agents extract and assess, and code checks every citation. Every number leads back to the page, tag or transaction it came from.</p>
          <p>We start where we know the ground best, India's companies and carbon projects, and the platform covers every major registry worldwide.</p>
          <a href="mailto:info@sylithe.com" className="inline-block mt-2 rounded-full bg-[#1D2118] text-white px-6 py-3 text-base">Talk to us: info@sylithe.com</a>
        </div>
      </section>
      <CtaBand />
    </>
  );
}
