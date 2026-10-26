/* Shared display rules, also exercised by the standalone Node tests. */
(function(root) {
  "use strict";
  function distanceMeters(a,b) {
    if(!a || !b || ![a.latitude,a.longitude,b.latitude,b.longitude].every(Number.isFinite))return null;
    const radians=value=>value*Math.PI/180;
    const lat1=radians(a.latitude),lat2=radians(b.latitude);
    const h=Math.sin((lat2-lat1)/2)**2+Math.cos(lat1)*Math.cos(lat2)*Math.sin(radians(b.longitude-a.longitude)/2)**2;
    return 6371008.8*2*Math.asin(Math.sqrt(Math.max(0,Math.min(1,h))));
  }
  function smallCorrection(row,review) {
    const metres=review?.correction?distanceMeters(row,review.correction):null;
    return metres!==null && metres<10;
  }
  function decision(row,review) {
    if(review && (review.latitude!==row.latitude || review.longitude!==row.longitude))return "a_verifier";
    if(review?.decision==="mauvais")return "mauvais";
    return smallCorrection(row,review)?"bon":review?.decision || "a_verifier";
  }
  const rules={distanceMeters,smallCorrection,decision};
  if(typeof module!=="undefined" && module.exports)module.exports=rules;
  else root.CoordinateReviewRules=rules;
})(typeof window!=="undefined"?window:globalThis);
