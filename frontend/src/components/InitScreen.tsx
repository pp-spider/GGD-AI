import React from "react";

interface InitScreenProps {
  status: string;
}

const InitScreen: React.FC<InitScreenProps> = ({ status }) => {
  return (
    <div className="init-screen">
      <div className="acrylic-card init-card">
        <div className="spinner"></div>
        <h2>正在初始化</h2>
        <p className="status-text">{status}</p>
      </div>
    </div>
  );
};

export default InitScreen;
