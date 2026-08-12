<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:html="http://www.w3.org/1999/xhtml">
    <xsl:output method="xml" indent="no" omit-xml-declaration="yes"/> 
    <xsl:strip-space elements="*"/>

    <!-- identity transform -->
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="html">
        <xsl:apply-templates select="@*|node()"/> 
    </xsl:template>

    <xsl:template match="body">
        <div xmlns="http://www.tei-c.org/ns/1.0" xmlns:html="http://www.w3.org/1999/xhtml">
            <xsl:apply-templates/>
        </div>
    </xsl:template>
    
    <xsl:template match="span">
        <seg><xsl:apply-templates select="@*|node()"/></seg>
    </xsl:template>

    <xsl:template match="tbody">
        <xsl:copy-of select=".//*"></xsl:copy-of>
    </xsl:template>

    <!-- Specific template to match 'p' elements and possibly add the 'ana' attribute -->
    <xsl:template match="p">
        <xsl:copy>
            <!-- Copy all attributes -->
            <xsl:apply-templates select="@*"/>
            
            <!-- Conditionally add 'ana' attribute -->
            <xsl:if test="3 >= string-length(normalize-space(.)) and contains(., '*')">
                <xsl:attribute name="ana">star-delimiter</xsl:attribute>
            </xsl:if>
            
            <!-- Copy child nodes -->
            <xsl:apply-templates select="node()"/>
        </xsl:copy>
    </xsl:template>
    
    <!-- Match <a> and convert to <ref> -->
    <xsl:template match="a">
        <ref>
            <xsl:apply-templates select="@*|node()"/>
        </ref>
    </xsl:template>
    
    <!-- Match href and convert to target -->
    <xsl:template match="@href">
        <xsl:attribute name="target">
            <xsl:value-of select="."/>
        </xsl:attribute>
    </xsl:template>
    
    <!-- Match id and convert to xml:id -->
    <xsl:template match="@id">
        <xsl:attribute name="xml:id">
            <xsl:value-of select="."/>
        </xsl:attribute>
    </xsl:template>
    
    <!-- Remove class attributes -->
    <xsl:template match="@class" />
    
    <!-- Match italic tags -->               
    <xsl:template match="em | i">
        <emph style="font-style: italic">
            <xsl:apply-templates/>                     
        </emph>                   
    </xsl:template>
    
    <!-- Match bold tags -->
    <xsl:template match="strong | b">
        <emph style="font-style: bold">
            <xsl:apply-templates/>                     
        </emph>                   
    </xsl:template>

    <!-- Transform <ol> into <list> -->
    <xsl:template match="ol">
        <list rend="numbered">
            <xsl:apply-templates select="@*|node()"/>
        </list>
    </xsl:template>

    <!-- Transform <ol> into <list> -->
    <xsl:template match="ul">
        <list rend="bulleted">
            <xsl:apply-templates select="@*|node()"/>
        </list>
    </xsl:template>

    <!-- Transform <li> into <item> -->
    <xsl:template match="li">
        <item>
            <xsl:apply-templates select="@*|node()"/>
        </item>
    </xsl:template>


    <!-- match elements with 'style' attribute containing 'font-style' other than 'normal' -->
    <xsl:template match="*[@style[contains(., 'font-style') and not(contains(., 'font-style: normal'))]]">
        <emph>
            <xsl:attribute name="style">
                <!-- extract 'font-style' property -->
                <xsl:value-of select="concat('font-style: ', substring-before(substring-after(@style, 'font-style:'), ';'))"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </emph>
    </xsl:template>
    <xsl:template match="p[@style[contains(., 'font-style') and not(contains(., 'font-style: normal'))]]">
        <p>
            <emph>
                <xsl:attribute name="style">
                    <!-- extract 'font-style' property -->
                    <xsl:value-of select="concat('font-style: ', substring-before(substring-after(@style, 'font-style:'), ';'))"/>
                </xsl:attribute>
                <xsl:apply-templates/>
            </emph>
        </p>
    </xsl:template>
    
    <!--<xsl:template match="*[@style[contains(., 'font-weight') and not(contains(., 'font-weight: normal'))]]">
        <emph>
            <xsl:attribute name="style">
                <xsl:value-of select="concat('font-weight: ', substring-before(substring-after(@style, 'font-weight:'), ';'))"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </emph>
    </xsl:template>-->

    <xsl:template match="span[@style[contains(., 'font-weight') and not(contains(., 'font-weight: normal'))]]">
        <seg>
            <emph>
                <xsl:attribute name="style">
                    <xsl:value-of select="concat('font-weight: ', substring-before(substring-after(@style, 'font-weight:'), ';'))"/>
                </xsl:attribute>
                <xsl:apply-templates/>
            </emph>
        </seg>
    </xsl:template>

    <!-- match h1-h6 elements -->
    <xsl:template match="h1 | h2 | h3 | h4 | h5 | h6">
        <head>
            <xsl:attribute name="type">
                <xsl:value-of select="name()"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </head>
    </xsl:template>

    <!-- Transform <img> tags -->
    <xsl:template match="img">
        <figure>
            <graphic>
                <xsl:attribute name="url">
                    <xsl:value-of select="@src"></xsl:value-of>
                </xsl:attribute>
                <xsl:apply-templates/>
            </graphic>
        </figure>
    </xsl:template>


</xsl:stylesheet>