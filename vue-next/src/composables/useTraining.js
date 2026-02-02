gsap.registerPlugin(ScrollTrigger);

const cards = document.querySelectorAll(".card");

cards.forEach((card, i) => {
  gsap.to(card, {
    scrollTrigger: {
      trigger: card,
      start: "left center",
      end: "right center",
      scrub: true,
      horizontal: true,
    },
    rotateY: 0,
    scale: 1.05,
    ease: "power2.out",
  });
});
