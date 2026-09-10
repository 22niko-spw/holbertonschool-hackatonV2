import React from 'react';

/** Pixel-art mark. Pass the application's existing theme state. */
export default function TaupeLogo({ size = 24, theme = 'light', className = '', decorative = false }) {
  const colors = theme === 'dark'
    ? { edge: '#c0af99', fur: '#877b6d', shine: '#a89a85', cheek: '#c6b296' }
    : { edge: '#393332', fur: '#756b62', shine: '#988b7b', cheek: '#b4a08a' };

  return (
    <svg width={size} height={size} viewBox="0 0 32 32" shapeRendering="crispEdges"
      className={className} style={{ display: 'block', flexShrink: 0 }}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative ? true : undefined}
      aria-label={decorative ? undefined : 'La Taupe'}>
  <path fill={colors.edge} d="M12 3h8v2h4v3h3v4h2v13h-3v3H6v-3H3V12h2V8h3V5h4Z"/>
  <path fill={colors.fur} d="M12 5h8v2h4v3h2v4h1v9h-3v3H8v-3H5v-9h1v-4h2V7h4Z"/>
  <path fill={colors.shine} d="M12 7h8v2h-8v2H9v3H7v-4h3V9h2Z"/>
  <path fill={colors.cheek} d="M12 16h8v2h4v5h-3v3H11v-3H8v-5h4Z"/>
  <path fill="#241f20" d="M8 13h4v4H8zM20 13h4v4h-4z"/>
  <path fill="#fff4dd" d="M8 13h1v1H8zM20 13h1v1h-1z"/>
  <path fill="#863c43" d="M12 18h8v2h2v4h-2v2h-8v-2h-2v-4h2Z"/>
  <path fill="#ee8b8a" d="M12 20h8v4h-8Z"/>
  <path fill="#ffb5a3" d="M12 19h7v2h-7Z"/>
  <path fill="#9c444c" d="M12 22h2v2h-2zM18 22h2v2h-2z"/>
    </svg>
  );
}
