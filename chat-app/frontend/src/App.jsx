import { useState, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';

function App() {
  const [pseudo, setPseudo] = useState('Anonyme');
  const [texte, setTexte] = useState('');
  const [messages, setMessages] = useState([]);
  const socketRef = useRef(null);

  useEffect(() => {
    const socket = io('http://127.0.0.1:5050');
    socketRef.current = socket;

    socket.on('historique', (anciens) => {
      setMessages(anciens);
    });

    socket.on('nouveau_message', (message) => {
      setMessages((precedents) => [...precedents, message]);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const envoyer = () => {
    if (!texte.trim()) return;
    socketRef.current.emit('message_envoye', { pseudo, texte });
    setTexte('');
  };

  return (
    <div style={{ maxWidth: 500, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1>Salon de discussion</h1>

      <p>
        Pseudo :{' '}
        <input value={pseudo} onChange={(e) => setPseudo(e.target.value)} />
      </p>

      <div style={{ border: '1px solid #ccc', height: 250, overflowY: 'auto', padding: 8 }}>
        {messages.map((m, i) => (
          <p key={i}>
            <strong>{m.pseudo}</strong> : {m.texte}
          </p>
        ))}
      </div>

      <input
        value={texte}
        onChange={(e) => setTexte(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && envoyer()}
        placeholder="Ecris un message..."
      />
      <button onClick={envoyer}>Envoyer</button>
    </div>
  );
}

export default App;
