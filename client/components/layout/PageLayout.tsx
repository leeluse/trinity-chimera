"use client";

import { ReactNode, Children, isValidElement } from "react";
import PanelContainer from "../panel/PanelContainer";

interface PageLayoutProps {
  children: ReactNode;
  fullHeight?: boolean;
  isRightSticky?: boolean;
  rightWidth?: string;
}

// Sub-components for semantic slotting
const Main = ({ children }: { children: ReactNode }) => <>{children}</>;
const Side = ({ children }: { children: ReactNode }) => <>{children}</>;

export default function PageLayout({ 
  children, 
  fullHeight = true, // Default to true for unified app feel
  rightWidth = "lg:w-[400px]"
}: PageLayoutProps) {
  // Extract slots from children
  let mainContent: ReactNode = null;
  let sideContent: ReactNode = null;

  Children.forEach(children, (child) => {
    if (isValidElement(child)) {
      const anyChild = child as any;
      if (anyChild.type === Main) mainContent = anyChild.props.children;
      if (anyChild.type === Side) sideContent = anyChild.props.children;
    }
  });

  // Fallback: if no slots used, treat all children as main
  if (!mainContent && !sideContent) {
    mainContent = children;
  }

  return (
    <div className="min-h-screen transition-colors duration-300">
      <main className={`ml-[72px] ${fullHeight ? 'h-screen' : 'min-h-screen'} flex flex-col overflow-hidden`}>
        <div className={`flex flex-col lg:flex-row flex-1 min-h-0 overflow-hidden`}>
          {/* Main Content Area */}
          <div className={`flex-1 min-w-0 overflow-y-auto no-scrollbar`}>
            {mainContent}
          </div>

          {/* Optional Right Panel Slot */}
          {sideContent && (
            <PanelContainer width={rightWidth}>
              {sideContent}
            </PanelContainer>
          )}
        </div>
      </main>
    </div>
  );
}

PageLayout.Main = Main;
PageLayout.Side = Side;