import { useEffect, useRef } from "react";

/**
 * useScrollReveal Purpose
 *
 * A small hook that makes elements animate into view when the user scrolls.
 * 
 * Usage:
 *   const ref = useScrollReveal();
 *   <section ref={ref}>
 *     <div className="reveal">...</div>
 *   </section>
 */

export default function useScrollReveal(threshold = 0.15) {
  const ref = useRef(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReduced) {
      // Immediately show everything – no animation
      if (ref.current) {
        ref.current
          .querySelectorAll(".reveal")
          .forEach((el) => el.classList.add("is-visible"));
      }
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target); // fire once
          }
        });
      },
      { threshold }
    );

    const elements = ref.current
      ? ref.current.querySelectorAll(".reveal")
      : [];
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [threshold]);

  return ref;
}
