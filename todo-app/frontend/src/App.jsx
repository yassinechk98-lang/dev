import { useState } from 'react';

function App() {
  const [taches, setTaches] = useState([
    { id: 1, titre: "Acheter du pain", terminee: false },
    { id: 2, titre: "Reviser React", terminee: true },
    { id: 3, titre: "Faire du sport", terminee: false },
  ]);

  return (
    <div>
      <h1>Ma Todo-list</h1>
      <ul>
        {taches.map((tache) => (
          <li key={tache.id}>
            {tache.titre} {tache.terminee ? "✅" : "❌"}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;
