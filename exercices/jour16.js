const prenom = "Yassine";
let compteur = 0;
console.log(`Prenom : ${prenom}, compteur : ${compteur}`);
const taches = ["Acheter du pain", "Reviser JS", "Faire du sport"];
for (const t of taches) {
     console.log(t); }
      const estMajeur = (age) => age >= 18;
console.log(estMajeur(27));
console.log(estMajeur(15));
async function recupererTaches() {
    const reponse = await fetch("http://localhost:5000/taches");
     const donnees = await reponse.json();
      console.log(donnees);}
recupererTaches();      
