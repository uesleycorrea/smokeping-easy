/* smokeping-easy — About tab.
 * Static content driven by i18n. Values below (repo URL and the event details)
 * are the only things you edit by hand before publishing / presenting. */
function aboutApp() {
  return {
    project: {
      name: "smokeping-easy",
      version: "1.2.0",
      repo: "https://github.com/uesleycorrea/smokeping-easy",
      license_url: "https://www.gnu.org/licenses/gpl-3.0.html"
    },
    author: {
      name: "Uesley Correa",
      company: "Telecom ISP Solutions",
      site: "https://telecomisp.solutions"
    },
    tech: [
      { name: "Smokeping", url: "https://oss.oetiker.ch/smokeping/" },
      { name: "FastAPI", url: "https://fastapi.tiangolo.com/" },
      { name: "Alpine.js", url: "https://alpinejs.dev/" },
      { name: "Chart.js", url: "https://www.chartjs.org/" },
      { name: "Docker", url: "https://www.docker.com/" },
      { name: "nginx", url: "https://nginx.org/" }
    ],

    t(k, p) { return this.$store.i18n.t(k, p); },
    init() { /* static */ },

    get issuesUrl() { return this.project.repo + "/issues/new"; },
    get prUrl() { return this.project.repo + "/pulls"; }
  };
}
