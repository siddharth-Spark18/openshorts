import { useEffect, useRef } from 'react';

// The checkout buttons show a spinner and disable themselves until the
// browser leaves for Stripe. Coming back with the back button, Safari and
// mobile browsers restore the page from the back/forward cache with that
// state intact, so every plan stays disabled until a reload. `pageshow` with
// `persisted` is that restore: put the buttons back.
export function useBackFromStripe(reset) {
  const resetRef = useRef(reset);
  useEffect(() => { resetRef.current = reset; });
  useEffect(() => {
    const onShow = (e) => { if (e.persisted) resetRef.current(); };
    window.addEventListener('pageshow', onShow);
    return () => window.removeEventListener('pageshow', onShow);
  }, []);
}
