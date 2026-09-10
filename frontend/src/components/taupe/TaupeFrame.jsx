import React, { useState } from 'react';
import restingMole from './assets/taupe-repos.png';
import tongueMole from './assets/taupe-langue.png';
import './taupe.css';

/** Wrap only the existing dropzone; keep its upload handlers on the child. */
export default function TaupeFrame({ children, theme, className = '', style }) {
  const [tongueOut, setTongueOut] = useState(false);
  const [tongueReady, setTongueReady] = useState(false);

  return (
    <div className={`taupe-frame ${className}`} data-theme={theme} style={style}>
      <button
        className="taupe-mascot"
        type="button"
        aria-label="Faire tirer la langue à la taupe"
        aria-pressed={tongueOut}
        data-tongue={tongueOut}
        data-ready={tongueReady}
        onClick={(event) => {
          event.stopPropagation();
          setTongueOut((previous) => !previous);
        }}
      >
        <span className="taupe-mascot__cutout" aria-hidden="true">
          <img className="taupe-mascot__image" src={restingMole} alt="" width="1254" height="1254" draggable={false} />
          <img
            className="taupe-mascot__image taupe-mascot__tongue"
            src={tongueMole}
            alt=""
            width="1254"
            height="1254"
            draggable={false}
            onLoad={() => setTongueReady(true)}
            onError={() => setTongueReady(false)}
          />
        </span>
      </button>
      {children}
    </div>
  );
}
