import React from "react";
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }
  componentDidCatch(error, errorInfo) {
    this.setState({ hasError: true, error: error, errorInfo: errorInfo });
    fetch("http://localhost:5000/api/log-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: error.toString(), info: errorInfo.componentStack }),
    }).catch(e => console.log(e));
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "20px", background: "white", color: "red", fontFamily: "monospace", zIndex: 9999, position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
          <h2>Something went wrong.</h2>
          <details style={{ whiteSpace: "pre-wrap" }}>
            {this.state.error && this.state.error.toString()}
            <br />
            {this.state.errorInfo.componentStack}
          </details>
        </div>
      );
    }
    return this.props.children;
  }
}
