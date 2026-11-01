// Preserve entry links from the original B Site; demo behavior remains unchanged.
(()=>{const aliases={dashboard:'student/home',paper:'student/papers',tutor:'student/tutor',knowledge:'student/knowledge'};const target=aliases[location.hash.slice(1)];if(target)history.replaceState(null,'','#'+target)})();
